#!/usr/bin/env python3
"""Structural safety check for SQL, meant to run before a statement reaches a real database.

Two modes, and the difference matters:

  * sqlglot installed  -> the statement is parsed and the whole tree is walked.
    A write hidden inside a CTE is found because the walk does not care where
    the node sits.
  * sqlglot missing    -> a conservative pattern scan runs instead. It is noisy
    by design and it CANNOT see structure, so an OK verdict in this mode means
    "nothing obvious matched", not "safe".

Usage:
    python3 check_sql.py "SELECT * FROM users LIMIT 10"
    python3 check_sql.py --file query.sql
    python3 check_sql.py --file migration.sql --allow-write
    python3 check_sql.py --file q.sql --json

Exit codes: 0 = OK, 1 = warnings only, 2 = blocking findings, 3 = could not parse.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

try:  # optional, but the whole point of the script
    import sqlglot
    from sqlglot import exp

    HAVE_SQLGLOT = True
    PARSER = f"sqlglot {getattr(sqlglot, '__version__', 'unknown')}"
except ImportError:  # pragma: no cover - depends on environment
    HAVE_SQLGLOT = False
    PARSER = "fallback pattern scan - verdict is NOT authoritative"

BLOCK = "BLOCK"
WARN = "WARN"

# Node types that write, in any position in the tree.
WRITE_NODES = ("Insert", "Update", "Delete", "Merge")
# Node types that change schema or permissions.
DDL_NODES = ("Drop", "Create", "Alter", "TruncateTable", "Grant", "Revoke")


class Finding:
    def __init__(self, severity: str, code: str, message: str, hint: str = ""):
        self.severity = severity
        self.code = code
        self.message = message
        self.hint = hint

    def as_dict(self) -> dict:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
        }


def _node_names(tree) -> set:
    """Every node class name in the tree, so lookups do not depend on sqlglot's class layout."""
    return {type(node).__name__ for node in tree.walk()}


def check_with_sqlglot(sql: str, allow_write: bool) -> tuple[list, str]:
    findings: list[Finding] = []

    try:
        statements = [s for s in sqlglot.parse(sql) if s is not None]
    except Exception as err:  # noqa: BLE001 - any parse error is a refusal, not a crash
        return ([Finding(BLOCK, "unparseable", f"Statement did not parse: {err}",
                         "A statement you cannot parse is a statement you cannot vouch for.")],
                "unparseable")

    if not statements:
        return ([Finding(BLOCK, "empty", "No statement found.", "")], "empty")

    if len(statements) > 1:
        findings.append(Finding(
            BLOCK, "multiple_statements",
            f"{len(statements)} statements in one string.",
            "Split them. Multiple statements in one string is the classic injection shape - "
            "the payload is the second one.",
        ))

    for stmt in statements:
        names = _node_names(stmt)
        root = type(stmt).__name__

        write_hits = sorted(names & set(WRITE_NODES))
        if write_hits and not allow_write:
            where = "as the root statement" if root in WRITE_NODES else "nested inside the statement"
            findings.append(Finding(
                BLOCK, "write_node",
                f"Write operation ({', '.join(write_hits)}) found {where}.",
                "Root-keyword classification misses the nested case entirely - this is why the "
                "whole tree is walked.",
            ))

        ddl_hits = sorted(names & set(DDL_NODES))
        if ddl_hits:
            findings.append(Finding(
                BLOCK, "ddl",
                f"Schema or permission change: {', '.join(ddl_hits)}.",
                "Irreversible in place. Run it as a reviewed migration, not as an ad-hoc query.",
            ))

        # UPDATE / DELETE with no WHERE - only relevant when writes are allowed at all.
        for node in stmt.find_all(exp.Update, exp.Delete):
            if not node.args.get("where"):
                findings.append(Finding(
                    BLOCK, "unqualified_write",
                    f"{type(node).__name__.upper()} with no WHERE clause - affects every row.",
                    "If that is genuinely the intent, say so explicitly in the review; it almost never is.",
                ))

        # SELECT ... INTO creates a table despite the SELECT root.
        for node in stmt.find_all(exp.Select):
            if node.args.get("into"):
                findings.append(Finding(
                    BLOCK, "select_into",
                    "SELECT ... INTO creates a new table despite the SELECT root.",
                    "Use CREATE TABLE AS in a reviewed migration if the table is wanted.",
                ))

        if "Lock" in names or re.search(r"\bFOR\s+(UPDATE|SHARE|NO\s+KEY\s+UPDATE)\b", sql, re.I):
            findings.append(Finding(
                WARN, "row_locks",
                "SELECT ... FOR UPDATE/SHARE takes row locks.",
                "It reads, but it blocks other transactions. Fine inside a deliberate transaction, "
                "surprising anywhere else.",
            ))

        # sqlglot produces a Set node for SET statements; the regex is a backstop for
        # dialects it parses differently. The regex used to require a word boundary right
        # after "=", so "SET search_path = evil" (with spaces) slipped through as OK -
        # the exact case references/postgres-patterns.md says must be rejected.
        # Anchored to the start of a statement: "UPDATE users SET active = false" also
        # contains "SET x =", and an unanchored pattern blocks every UPDATE ever written.
        if "Set" in names or re.search(r"(?:^|;)\s*SET\s+(SESSION\s+|LOCAL\s+)?[\w.]+\s*(=|\bTO\b)",
                                       sql, re.I):
            findings.append(Finding(
                BLOCK, "session_set",
                "SET changes session behaviour for everything that follows.",
                "Session-level settings leak past this query. Use SET LOCAL inside a transaction, "
                "or set it in the connection configuration.",
            ))

        # Cartesian products: a join with no ON/USING condition.
        for join in stmt.find_all(exp.Join):
            if not join.args.get("on") and not join.args.get("using"):
                kind = (join.side or join.kind or "").upper()
                if "CROSS" not in kind:
                    findings.append(Finding(
                        WARN, "cartesian_join",
                        "Join without ON/USING - row count multiplies.",
                        "Usually shows up later as 'the query never finished'. If a cross join is "
                        "intended, write CROSS JOIN so the next reader knows it was deliberate.",
                    ))

        # Unbounded scan: a top-level SELECT with no LIMIT and no WHERE that reads a real
        # table. Reading only from a CTE or subquery is bounded by whatever built it, so
        # warning there is noise - and it fired on the control case in the reference doc.
        if root == "Select" and not stmt.args.get("limit") and not stmt.args.get("where"):
            cte_names = {cte.alias_or_name for cte in stmt.find_all(exp.CTE)}
            reads_real_table = any(t.name and t.name not in cte_names
                                   for t in stmt.find_all(exp.Table))
            if reads_real_table and not list(stmt.find_all(exp.AggFunc)):
                findings.append(Finding(
                    WARN, "unbounded_scan",
                    "SELECT with neither WHERE nor LIMIT.",
                    "Fine on 10k rows, an outage on a billion. Ask for the row count instead of guessing.",
                ))

        # Only flag DISTINCT that sits on the same SELECT as the join. A DISTINCT inside a
        # CTE is usually the correct fix for row multiplication, and flagging it talks the
        # reviewer out of the right answer.
        distinct_over_join = any(select.args.get("distinct") and select.args.get("joins")
                                 for select in stmt.find_all(exp.Select))
        if distinct_over_join:
            findings.append(Finding(
                WARN, "distinct_over_join",
                "DISTINCT combined with a join.",
                "DISTINCT often hides a join that multiplies rows rather than fixing it. "
                "Check the join keys before accepting the duplicates as normal.",
            ))

    return findings, "parsed"


FALLBACK_BLOCK_PATTERNS = [
    (r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|MERGE\s+INTO)\b", "write_node",
     "Write operation matched by pattern."),
    (r"\b(DROP|TRUNCATE|ALTER|CREATE)\s+(TABLE|SCHEMA|DATABASE|INDEX|VIEW|ROLE|USER)\b", "ddl",
     "Schema change matched by pattern."),
    (r"\b(GRANT|REVOKE)\b", "grant", "Permission change matched by pattern."),
    (r"\bSELECT\b[\s\S]*\bINTO\s+\w+", "select_into", "SELECT ... INTO matched by pattern."),
    (r"(?:^|;)\s*SET\s+(SESSION\s+|LOCAL\s+)?[\w.]+\s*(=|\bTO\b)", "session_set",
     "Session SET matched by pattern."),
]

FALLBACK_WARN_PATTERNS = [
    (r"\bFOR\s+(UPDATE|SHARE)\b", "row_locks", "Row-level locking matched by pattern."),
    (r";\s*\S", "multiple_statements", "More than one statement may be present."),
]


def check_fallback(sql: str, allow_write: bool) -> tuple[list, str]:
    findings = [Finding(
        WARN, "no_parser",
        "sqlglot is not installed - this is a pattern scan, not structural validation.",
        "Install it with `pip install sqlglot`. Without it, a write hidden inside a CTE will "
        "not be reliably detected, and an OK verdict means only that nothing obvious matched.",
    )]
    for pattern, code, message in FALLBACK_BLOCK_PATTERNS:
        if re.search(pattern, sql, re.I):
            if code == "write_node" and allow_write:
                continue
            findings.append(Finding(BLOCK, code, message, ""))
    for pattern, code, message in FALLBACK_WARN_PATTERNS:
        if re.search(pattern, sql, re.I):
            findings.append(Finding(WARN, code, message, ""))
    return findings, "fallback"


def verdict_of(findings) -> str:
    if any(f.severity == BLOCK for f in findings):
        return BLOCK
    if any(f.severity == WARN for f in findings):
        return WARN
    return "OK"


def render(findings, verdict: str, authoritative: bool = True) -> str:
    if authoritative:
        label = PARSER
    elif HAVE_SQLGLOT:
        label = "forced fallback pattern scan - NOT authoritative"
    else:
        label = PARSER  # already says sqlglot is missing and the verdict is not authoritative
    lines = [f"VERDICT: {verdict}", f"(parser: {label})", ""]
    blockers = [f for f in findings if f.severity == BLOCK]
    warnings = [f for f in findings if f.severity == WARN]
    if blockers:
        lines.append("BLOCKERS")
        for i, f in enumerate(blockers, 1):
            lines.append(f"{i}. [{f.code}] {f.message}")
            if f.hint:
                lines.append(f"   {f.hint}")
        lines.append("")
    if warnings:
        lines.append("WARNINGS")
        for i, f in enumerate(warnings, 1):
            lines.append(f"{i}. [{f.code}] {f.message}")
            if f.hint:
                lines.append(f"   {f.hint}")
        lines.append("")
    if not blockers and not warnings:
        lines.append("Nothing matched. Read the query yourself as well - this checks structure, "
                     "not whether the WHERE clause means what the author thought.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sql", nargs="?", help="SQL string to check")
    parser.add_argument("--file", "-f", help="read SQL from a file")
    parser.add_argument("--allow-write", action="store_true",
                        help="reviewing a deliberate write: do not block on INSERT/UPDATE/DELETE, "
                             "but still block unqualified ones")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--force-fallback", action="store_true",
                        help="run the pattern scan even when sqlglot is installed, so the "
                             "degraded path can be tested rather than taken on trust")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as handle:
            sql = handle.read()
    elif args.sql:
        sql = args.sql
    else:
        sql = sys.stdin.read()

    if not sql.strip():
        print("No SQL given.", file=sys.stderr)
        return 3

    checker = check_with_sqlglot if (HAVE_SQLGLOT and not args.force_fallback) else check_fallback
    findings, status = checker(sql, args.allow_write)
    verdict = verdict_of(findings)

    authoritative = HAVE_SQLGLOT and not args.force_fallback
    if args.json:
        print(json.dumps({
            "verdict": verdict,
            "parser": PARSER if (authoritative or not HAVE_SQLGLOT)
                      else "forced fallback pattern scan",
            "authoritative": authoritative,
            "status": status,
            "findings": [f.as_dict() for f in findings],
        }, indent=2))
    else:
        print(render(findings, verdict, authoritative))

    if status == "unparseable":
        return 3
    return {"BLOCK": 2, "WARN": 1, "OK": 0}[verdict]


if __name__ == "__main__":
    sys.exit(main())
