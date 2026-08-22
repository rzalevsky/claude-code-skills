# Enforcing read-only access in PostgreSQL

Read this when the review has to become a running constraint — an agent, an MCP server, a scheduled job — rather than a one-off opinion about one query.

## Layer 2: the database says no

Layer 1 (parsing) can be wrong. A parser has bugs, a dialect has corners, and the model writing the SQL is creative. Layer 2 is the one that holds anyway, and it is three lines of setup.

```sql
-- per connection
SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY;

-- per transaction, so a runaway query cannot hold resources indefinitely
BEGIN;
SET LOCAL statement_timeout = '5s';
SELECT ...;
COMMIT;
```

In a read-only transaction PostgreSQL rejects INSERT, UPDATE, DELETE, and most DDL itself. The error comes from the engine, not from your code, which is exactly what you want: it is the layer that does not depend on your reasoning being correct.

`SET LOCAL` matters more than it looks. Plain `SET` leaks into everything that follows on that connection, so a timeout you meant for one query silently becomes a property of the session — and in a pooled connection, of whoever gets it next.

## Least privilege beats clever validation

```sql
CREATE ROLE agent_ro LOGIN PASSWORD '...';
REVOKE ALL ON DATABASE app FROM PUBLIC;
GRANT CONNECT ON DATABASE app TO agent_ro;
GRANT USAGE ON SCHEMA public TO agent_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_ro;

-- tables created later are not covered by the grant above
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO agent_ro;
```

Grant per schema, not per database. Name the schemas the role may read; a role that can read everything will eventually read something it should not have, and no amount of query validation fixes a permissions model that says yes.

The `ALTER DEFAULT PRIVILEGES` line is the one people forget. Without it, the grant covers today's tables and silently excludes tomorrow's — which surfaces as a confusing permission error weeks later, long after anyone remembers this setup.

## Layer 1: what an allow-list actually looks like

Deny-lists fail by omission — they enumerate the attacks you already thought of. An allow-list fails by rejecting something legitimate, which is a support ticket rather than an incident.

```python
import sqlglot
from sqlglot import exp

ALLOWED_ROOTS = (exp.Select, exp.Union, exp.Describe)
FORBIDDEN_ANYWHERE = (exp.Insert, exp.Update, exp.Delete, exp.Merge,
                      exp.Drop, exp.Create, exp.Alter, exp.Grant)

def is_read_only(sql: str) -> bool:
    statements = [s for s in sqlglot.parse(sql) if s is not None]
    if len(statements) != 1:                       # one statement, always
        return False
    stmt = statements[0]
    if not isinstance(stmt, ALLOWED_ROOTS):        # allow-list on the root
        return False
    if any(isinstance(node, FORBIDDEN_ANYWHERE)    # deny anywhere in the tree
           for node in stmt.walk()):
        return False
    if stmt.args.get("into"):                      # SELECT ... INTO
        return False
    return True
```

The `walk()` call is the whole idea. `isinstance(stmt, exp.Select)` is true for the CTE-delete example, and a validator built on that check alone hands the model a working DELETE.

## Cases worth having tests for

These are the ones that break naive validators. They need no database — parse and assert — which is why they belong in a test file that runs in CI on every commit.

| Statement | Must be | Why it is interesting |
|---|---|---|
| `WITH t AS (DELETE FROM users RETURNING *) SELECT * FROM t` | rejected | Root is SELECT, effect is DELETE |
| `SELECT * INTO copy FROM users` | rejected | Creates a table |
| `SELECT * FROM users FOR UPDATE` | rejected or warned | Reads, but locks rows |
| `SELECT 1; DROP TABLE users` | rejected | Second statement is the payload |
| `SET search_path = evil; SELECT * FROM users` | rejected | Changes which table "users" means |
| `SELECT * FROM users WHERE id = 1` | accepted | The control case — a validator that rejects everything is not a validator |
| `WITH t AS (SELECT 1) SELECT * FROM t` | accepted | Legitimate CTE; rejecting all CTEs is the lazy fix |

That last pair matters as much as the blocks. It is easy to write a validator that says no to everything and looks safe in tests; the accepted cases are what stop that from passing review.

## Timeouts and result size

A read-only query can still take a database down by returning too much or running too long.

- `statement_timeout` — a hard ceiling per transaction. Pick a number the caller can live with (a few seconds for interactive work).
- Result cap — enforce a row limit in the calling code, not only via `LIMIT` in the SQL. The model writes the SQL; the cap should not be something the model can remove.
- `EXPLAIN` before running an unfamiliar query on an unfamiliar table. The estimated row count is what turns "probably fine" into a number.
