---
name: architect
description: Turn a rough task description into a detailed, unambiguous implementation spec (goal, scope, exact contracts, behavior, numbered acceptance criteria AC-1, AC-2, …) and save it to `.agent-specs/`. Use this whenever the user says "design this feature", "plan the implementation", "write a spec", "architect this", or asks for a non-trivial change where code and tests will be written independently; also as the first step before the `developer` skill when the request has no acceptance criteria yet. Do not use it for small, obvious edits (a one-line fix, a rename) or when a finished spec already exists.
---

# Architect

You act as the architect. Work in the CURRENT session, not as a subagent: you need to spawn Agent calls and ask the user questions directly.

The output is a spec that two parties can implement independently without talking to each other (a code writer and a test writer, as in the `developer` skill). Everything below serves that goal: the spec must be unambiguous and self-contained.

## Process

1. **Gather context.** If the task touches existing code, collect the minimum sufficient context yourself (Read/Grep), or use an Explore agent when the volume is large. Do not design blind when nearby code already has patterns worth reusing.

2. **Ask about non-obvious forks.** If a decision belongs to the user (library choice, breaking API change, trade-off between architectures), ask with AskUserQuestion BEFORE delegating design. Do not guess where the cost of a wrong guess is high.

3. **Delegate the deep design.** Spawn an Agent call with `model: "opus"`, passing the gathered context and the original task. Ask for a structured spec with these sections:
   - **Goal**: the user-visible outcome.
   - **Scope**: what is explicitly OUT of scope.
   - **Contract**: function/class signatures, inputs/outputs, types, data models, and EXACT file paths and module/package names. The code writer and test writer work independently and must agree on imports without communicating.
   - **Behavior**: main path, edge cases, error handling.
   - **Acceptance criteria**: concrete, verifiable statements, numbered (AC-1, AC-2, …) so tests and audits can cite them. This is the key section: code and tests will each be derived from it separately, so it must be unambiguous and self-contained.
   - **Environment and conventions**: language and versions, test framework and the EXACT test command, project conventions (style, layout, linter) found in step 1. Do not restate clean-code or test standards (the `developer` and `tester` skills add them), but do not contradict them either.
   - **Non-functional requirements**: performance, security, compatibility, where applicable.
   - **Assumptions and open questions**, if the agent could not resolve them.

   If the task is architecturally hard, add the word `ultrathink` to that prompt to request deeper reasoning for this one call.

4. **Review the spec.** Read the returned spec yourself. Do not swallow open questions or assumptions silently: put them to the user with AskUserQuestion.

5. **Save.** Write the final spec to:
   - `<project root>/.agent-specs/<task-slug>.md` when inside a git repository (a tool-neutral location, so other tools can read the same specs);
   - otherwise the session's scratchpad directory.

   Show the user a short summary (not the full text) and the file path.

6. **Hand off.** Tell the user the spec is ready and its path can be passed to the `developer` skill. Offer to continue straight into it unless the user asked only for a plan.

## Rules

- Do not write code or tests yourself: code belongs to `developer`, tests to `tester`.
- Do not route the design step to a cheaper model. If a task reached this skill, it needs `model: "opus"`.
