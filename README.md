# claude-code-skills

Nine [Claude Code](https://docs.claude.com/en/docs/claude-code) skills, written while working through how skills actually behave. Five of them package something I had already built and had opinions about — SQL safety from an MCP server, extraction validation from an n8n workflow, process modelling and pre-automation audit from fifteen years of ERP work. The other four are the development workflow I use day to day: a spec-first, multi-agent process (`architect` → `developer` ↔ `tester`) and a UI design skill (`designer`).

**What these are:** personal skills, written and tested by one person, published so the craft is visible.

**What these are not:** a production rollout in an organisation. Nobody's accounting department depends on them. If you are reading this to judge whether I can design and validate this kind of thing, the code and the reasoning in each `SKILL.md` are the evidence — not a claim of scale.

## The skills

| Skill | What it does |
|---|---|
| [`sql-safety-review`](skills/sql-safety-review/) | Reviews SQL before it reaches a real database. Catches writes hidden inside CTEs, `SELECT ... INTO`, unqualified `DELETE`, session-level `SET`, row locks, cartesian joins. Parses with [sqlglot](https://github.com/tobymao/sqlglot) and walks the whole tree, because classifying by the first keyword misses the interesting cases. |
| [`bpmn-from-prose`](skills/bpmn-from-prose/) | Turns a described process into valid BPMN 2.0 with computed layout, openable in Camunda Modeler. The interview questions matter more than the notation: prose descriptions systematically omit the exceptions. |
| [`process-automation-audit`](skills/process-automation-audit/) | Audits a process *before* automating it — volume, exception rate, stability, ownership — and gives a go / fix-first / no-go verdict with a payback range. Includes where a model earns its place and where a rule is cheaper and more reliable. |
| [`structured-extraction`](skills/structured-extraction/) | Extracts document fields into a strict schema, with validation that stops the run instead of writing a doubtful value. Covers the locale traps that corrupt data silently — the decimal comma, ambiguous dates, thousands separators. |
| [`skill-doctor`](skills/skill-doctor/) | Lints a `SKILL.md`: frontmatter, description quality, body length, dead references, unreferenced files. Most skills that "do not work" have a description problem, and the failure is silent. |
| [`architect`](skills/architect/) | Turns a rough task into an unambiguous spec with numbered acceptance criteria (AC-1, AC-2, …), exact paths and signatures — written so that code and tests can be produced independently from it. Asks the user about the genuinely open forks before designing. |
| [`developer`](skills/developer/) | Orchestrates implementation of a spec in six phases: blind parallel writing of code and tests in isolated git worktrees, independent peer review (blocking / non-blocking findings), one fix pass and merge, then a test-and-fix loop capped at three iterations with failures routed as code-bug / test-bug / contract-mismatch. |
| [`tester`](skills/tester/) | The test side of the same process: writes tests from the acceptance criteria without reading the implementation, has them audited, runs the suite and classifies every failure. Never edits implementation code. |
| [`designer`](skills/designer/) | Designs interfaces (web, dashboards, terminal UIs, native) in three modes — create, audit, by example — and checks the result against real screenshots (`shots.sh`: mobile / tablet / desktop / dark) and an accessibility checklist. |

## Using them

Skills live in `~/.claude/skills/` (personal) or `.claude/skills/` (per project):

```bash
git clone https://github.com/rzalevsky/claude-code-skills.git
ln -s "$PWD/claude-code-skills/skills/sql-safety-review" ~/.claude/skills/sql-safety-review
```

Symlink only the ones you want. `developer`, `tester` and `architect` call each other, so install those three together; `developer` also relies on Claude Code's `isolation: "worktree"` option of the Agent tool. Claude reads the `description` in each skill's frontmatter and loads the skill when it matches what you are doing — you do not invoke them by name.

Optional dependencies, each with a working fallback:

```bash
pip install sqlglot      # sql-safety-review: without it, the check degrades to a pattern scan
pip install jsonschema   # structured-extraction: without it, a built-in subset of checks runs
```

Both scripts say in their output when they are running degraded, because a safety check that quietly weakens is worse than one that is absent. `structured-extraction` also picks whichever validator class the installed `jsonschema` actually has — 3.x, still shipped by several distributions, has no `Draft202012Validator`, and assuming it does turns a nice-to-have dependency into a crash on somebody else's machine.

## Running the checks

```bash
pip install pytest sqlglot jsonschema
pytest -q
```

32 tests, no database and no model required — the interesting failures in all three scripts live at the parser boundary, and a boundary you can test in isolation is one that stays correct. `test_every_skill_in_this_repo_lints_clean` runs `skill-doctor` over every other skill here, so the linter has to pass on the repository that ships it.

The four development-workflow skills are process instructions, not scripts: only `designer` ships a helper (`shots.sh`), and none of them has unit tests — they are linted by `skill-doctor` in CI, nothing more. Whether a process like this improves results is something I have used, not measured.

The test suite is also the honest record of what the scripts get wrong. Three of these tests exist because a bug got through: `SET search_path = evil` returned a clean OK (a regex needing a word boundary after `=`), the same rule then blocked every `UPDATE ... SET x = y` once it was fixed, and `DISTINCT` inside a CTE was reported as a smell when it was the correct fix.

## Where the material came from

- [`mcp-postgres-server`](https://github.com/rzalevsky/mcp-postgres-server) — a Python MCP server exposing PostgreSQL to a language model, with two independent safety layers. The structural rules in `sql-safety-review` are its validation logic, unpacked.
- [`n8n-automation-workflows`](https://github.com/rzalevsky/n8n-automation-workflows) — three self-hosted workflows on a local LLM. The fail-loudly principle in `structured-extraction` is its invoice intake, including the Polish decimal comma that broke it on day two.
- [`bpmn-process-models`](https://github.com/rzalevsky/bpmn-process-models) — AS-IS / TO-BE models of three processes common to ERP roll-outs.

## Licence

MIT — see [LICENSE](LICENSE).
