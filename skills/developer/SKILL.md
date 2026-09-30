---
name: developer
description: Implement a well-specified feature or fix through a multi-agent pipeline: blind parallel writing of code and tests in isolated git worktrees, independent peer review by two auditors, one fix pass and merge, then an automatic test-and-fix loop (max 3 iterations) with failure routing. Use this whenever the user says "implement this spec", "build this with the multi-agent process", "run developer", or hands over a spec with acceptance criteria (ideally from the `architect` skill). A raw request without a spec is sent through `architect` first. Do not use it for trivial edits, exploratory prototyping, or tasks where a single agent can just make the change.
---

# Developer

You act as the implementation orchestrator. Work in the CURRENT session, not as a subagent: you must spawn several parallel Agent calls and run the fix loop yourself. Subagents cannot spawn subagents, so nobody but the top-level session can orchestrate this.

Split of skills: `developer` owns CODE (roles code-writer, code-auditor, code-writer-fix, the "Code standard") and the end-to-end loop. `tester` owns TESTS (roles test-writer, test-auditor, test-writer-fix, test-runner, the "Test standard", the failure report format). Load the `tester` skill (Skill tool) at the start; take the test-side roles and standard from it.

Subagents do NOT see these files. Paste everything they need (the spec and the standards) into their prompts VERBATIM.

Models are set through the `model` parameter of the Agent tool ("opus", "sonnet", "haiku"). Default to `sonnet` and adjust to the actual complexity of the spec.

## Phase 0: check the input

If the input is NOT a spec (no explicit acceptance criteria or contract, just a raw request), first invoke the `architect` skill yourself with that request, wait for the finished spec, and use it as the single source of truth for all roles. Do not ask the user to do that step manually.

Check the git environment:
- If you are outside a git repository, or it has no commits, worktrees are unavailable. Warn the user up front and agree with them (in plain text) on either `git init` plus a first commit, or running Phase 1 without isolation (agents work in the shared tree sequentially, not in parallel).
- A worktree is created from `HEAD`: uncommitted changes in the main tree are invisible in it. Run `git status --short`; if the task depends on pending changes, ask the user to commit or stash them BEFORE starting, otherwise agents work on a stale base.

## Phase 1: blind parallel writing (fan-out)

In one message, make two parallel Agent calls:

- **code-writer**: input is ONLY the spec text + the "Code standard" (below) + the instruction "implement only the code for this spec, do not write tests". Never mention that tests are being written in parallel.
- **test-writer** (role from `tester`): input is ONLY the same spec text + the "Test standard" from `tester`, with the instructions from its role description. Never mention the code-writer.

Both calls use `isolation: "worktree"`, so each works in its own isolated repository copy and they cannot conflict on files. Record each result's worktree path and branch name.

When they finish, confirm the changes are committed on the worktree branch (`git -C <path> status --short`); if not, commit them yourself (`git -C <path> add -A && git -C <path> commit -m "..."`). Without a commit the Phase 3 merge transfers nothing.

Model: `sonnet` for the standard case; `haiku` if the spec clearly describes a small mechanical change; `opus` only if it is already evident that the task is architecturally harder than what should reach this skill (then also tell the user that `architect` perhaps should be re-run).

## Phase 2: independent peer review

In one message, make two parallel Agent calls:

- **code-auditor**: input is the spec + "Code standard" + the path to the code-writer's worktree. It does NOT see the test-writer or its tests. It checks conformance to the contract and acceptance criteria, edge cases from the spec, bugs, security, and compliance with the Code standard.
- **test-auditor** (role from `tester`): input and checks as in that role description; the path is the test-writer's worktree. It does NOT see the code.

Every auditor must label each finding **blocking** or **non-blocking** (criteria for code are in "Code audit severity" below; for tests, in `tester`).

Model: `sonnet` for both; `opus` if the code or tests are critical or security-sensitive.

## Phase 3: fix pass and merge

- If the code-auditor has **blocking** findings, make one more Agent call with the same model, in the role "code-writer-fix", WITHOUT `isolation` (a new worktree would be created from `HEAD` and would not contain the writer's work). In the prompt give the absolute path of the code-writer's existing worktree and require working only inside it: spec + Code standard + original code + blocking findings, patched in place. Then commit the result on that branch.
- Likewise, blocking findings from the test-auditor go to `test-writer-fix` (role from `tester`) in the test-writer's worktree.
- This is ONE fix pass with no re-audit: regressions will be caught by the test run in Phase 4. Non-blocking findings are not fixed; they go into the final report (Phase 5).
- Then merge both branches into the main tree (`git merge <branch>`; usually conflict-free because code and tests are different files; on a conflict, resolve it yourself or, if ambiguous, ask the user), and remove the worktrees and branches (`git worktree remove`, `git branch -d`).

## Phase 4: test run and fix loop

Run **test-runner** (role from `tester`, a fresh agent) in the merged main tree. It returns a report in the `tester` format. Then:
1. All green: go to Phase 5.
2. Failures: route by verdict.
   - `code-bug`: a fresh `code-writer-fix` in the main tree, given the spec + Code standard + current code + the output of the failing tests.
   - `test-bug`: a fresh `test-writer-fix` (role from `tester`) in the main tree.
   - `contract-mismatch`: decide by the rule in `tester` (by the spec text; if the spec is silent, fix the tests and put the spec gap in the final report).
   - `environment` / `unclear`: investigate yourself or, if ambiguous, ask the user.
3. Run the tests again.

**Limit: at most 3 "fix, then run" iterations.** If the tests are still red after the third, stop the loop and report to the user: what exactly fails, what was already tried, a hypothesis about the cause, and a recommendation (for example, escalating the diagnosis to a stronger model manually).

## Phase 5: final report

Briefly tell the user: what was implemented, how many iterations it took, which models were used at each step, and which non-blocking audit findings remain open (style, suggestions for later) that did not block the test run.

## Code audit severity

- **blocking**: violation of the contract or acceptance criteria, a bug, a security problem, a missed edge case from the spec; silently swallowed errors, noticeable duplication, an SRP violation that really hampers understanding.
- **non-blocking**: names, a function a couple of lines too long, style, improvement suggestions that do not affect correctness.

## Code standard (Clean Code)

For code-writer, code-writer-fix, and as criteria for code-auditor. Paste into the prompt verbatim.

Priority: the project's own conventions (style, layout, linter, established patterns) override this standard. The standard is not a reason to rewrite code outside the task.

1. **SRP.** Every module, class, and function has one responsibility. No "god" objects or bloated methods mixing business logic, parsing, I/O, and presentation.
2. **Compact functions.** Aim for 20-30 lines or fewer, one level of abstraction, nesting of conditions and loops no deeper than 2-3 levels; extract complex logic into helper functions with clear names.
3. **Meaningful names.** Names state intent. No single-letter variables (except trivial indices in short loops), unclear abbreviations, or empty suffixes (`Data`, `Info`, `Manager`) that do not stand for a concrete pattern.
4. **KISS, DRY, YAGNI.** The simplest transparent implementation, without needless indirection. Shared logic lives in one place. Nothing beyond the spec: extra functionality and public API is a defect (under blind parallel work it also diverges from the tests).
5. **Separation of concerns.** Data storage, business logic, and presentation are isolated; dependencies are passed explicitly (parameters/constructors), with no hidden mutable global state.
6. **Explicit error handling.** Catch exceptions narrowly and with context; silent swallowing (empty catch/except) is not allowed. Use specific error types or a Result, not magic codes; put magic numbers and strings into named constants.
7. **Self-documenting code.** Code reads like prose. Comment only a non-obvious "why" (an API limitation, a bug workaround), never a restatement of the code. Delete commented-out and unused code.

## Rules

- Never let the code-writer and test-writer see each other, neither the code nor the fact the other exists, before Phase 3.
- Do not skip Phase 0: without a clear spec, blind fan-out almost guarantees code and tests that do not fit together.
