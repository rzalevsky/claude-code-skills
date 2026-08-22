---
name: bpmn-from-prose
description: Turn a prose description of how work actually gets done into a valid BPMN 2.0 diagram that opens in Camunda Modeler, bpmn.io, or Signavio — including the diagram layout, which is the part that is miserable to write by hand. Use this whenever someone describes a business process in words, an interview transcript, an email thread, or a bullet list and wants it modelled; whenever they ask for a process map, swimlane diagram, AS-IS or TO-BE model, or "can you draw this process"; whenever a procedure needs documenting before it is automated; and whenever an existing .bpmn file needs reviewing for notation mistakes. Use it even when the person says "just a quick flowchart" — the interview questions here are what turn a vague description into something the process owner will recognise.
---

# BPMN from prose

Somebody describes a process. You have to turn it into a diagram that the person who owns the process will look at and say "yes, that is what happens" — not "that is roughly what the procedure says should happen".

Two things make this hard, and neither is the notation. The first is that prose descriptions systematically omit the exceptions, which is where all the interesting work lives. The second is BPMNDI: BPMN files carry semantics and layout separately, and a file with perfect semantics and no layout opens as a blank canvas. The bundled script handles the layout so you can spend the effort on the first problem.

## The order of work

**1. Read the description and write down what is missing.** Do this before modelling anything. A first-pass description almost always leaves out: who does each step (not which department — which role), what happens when the check fails, how long a step waits and on what, where the work sits between steps, and how anyone knows the process finished. If you model only what was said, you produce a diagram of the happy path and the process owner will not recognise it.

**2. Ask the gaps as concrete questions.** Not "are there any exceptions?" — nobody can answer that. Ask "what happens when the invoice arrives without a PO number?" People answer specific questions accurately and general ones vaguely.

**3. Write the spec, generate, look at it.**

```bash
python3 scripts/build_bpmn.py spec.json -o process.bpmn --check-layout
python3 scripts/build_bpmn.py spec.json --validate-only   # structure check, no output file
```

`--check-layout` matters when you cannot open a modeller: a spec that validates perfectly can still lay out badly, most often when a task is joined from a late branch and gets pushed far to the right. The flag reports overlaps, shapes outside their lane, and over-stretched edges — the things a reviewer notices in a second and an agent cannot see at all.

**What this generator cannot build**, so you find out now rather than mid-model: boundary events (they need `attachedToRef`), and pools with message flows between organisations. For a deadline, use an exclusive gateway after the task; for another organisation, model what your process waits for and leave their internals out. Both are simplifications — say so next to the diagram.

Waiting events need their kind: `{"type": "intermediateCatchEvent", "event": "message"}`. A catch event with no event definition is not well-formed BPMN, and modellers draw it as a bare double circle.

The spec format is documented in the script's header — elements, flows, optional lanes. The validator catches unreachable steps, dead ends, gateways that neither split nor merge, unlabelled branches on an exclusive gateway, and unknown element types.

**4. Say what you inferred.** Every assumption you made to fill a gap goes in a short list next to the diagram. This is the part that makes the model reviewable: the process owner cannot correct an assumption they cannot see.

**When there is nobody to answer the questions** — a single request, no follow-up — model only what was described, and turn each gap into a specific question paired with the one-line edit that would answer it ("if a warranty claim can be refused at assessment, that is one flow: `g_ocena → t_wycena`"). Do not draw an unconfirmed branch: a diagram is read as a statement of fact about the process, and inventing an exception puts fiction in front of the owner. The rule that exceptions belong on the diagram applies to exceptions you were *told about*.

## Choosing elements

Most models need very few element types, and reaching for exotic ones usually signals that the process is not yet understood.

| Situation | Element |
|---|---|
| A person does the work | `userTask` |
| A system does it with no human involved | `serviceTask` |
| A physical action outside any system | `manualTask` |
| A decision with one outcome taken | `exclusiveGateway` |
| Branches that all run | `parallelGateway` |
| Waiting for something external — a reply, a date | `intermediateCatchEvent` |
| The trigger | `startEvent` |
| Each distinct outcome | `endEvent` — one per outcome, not one shared |

Separate end events for "invoice booked" and "invoice rejected" is not pedantry. Merging them hides that the process has two outcomes with different downstream consequences, and that distinction is usually the reason someone asked for the model.

## Notation mistakes worth catching

These show up constantly and each one has a specific consequence:

- **A task with two outgoing flows.** In BPMN that means both run at once. If a decision was meant, put in a gateway; otherwise you have documented parallelism nobody intended.
- **Unlabelled branches on an exclusive gateway.** The reader cannot tell which way the decision goes. Label them with the condition, not with "yes"/"no" alone where the question is not on the gateway.
- **Gateways that neither split nor merge.** One in, one out — pure noise. Delete it.
- **A gateway used as a task.** "Sprawdzenie kwoty" is work someone does; the gateway is the branch that follows it. Model the check as a task and the decision as the gateway.
- **A lane per department rather than per role.** Lanes answer "who does this", and "Księgowość" does not answer it if three roles in that department do different steps.
- **A model with no end event.** Usually means the outcome was never defined, which is worth surfacing rather than papering over.

`references/notation-rules.md` covers the trickier cases — loops and rework, timers and escalation, message flows between participants, when a subprocess earns its place.

## AS-IS and TO-BE

When both are wanted, model AS-IS first and completely, including the parts that are embarrassing — the re-typing, the spreadsheet that gets emailed around, the person who checks the same thing twice. A TO-BE built on a sanitised AS-IS improves a process nobody actually runs.

Then make TO-BE a *diff*, not a fresh drawing. For each change, say which bottleneck in the AS-IS it removes. A TO-BE that cannot be traced back step by step to a specific problem in the AS-IS is a wish list, and it will be read as one.

The honest test for a TO-BE: for each removed step, can you say what now catches the error that step used to catch? "The model extracts the fields" removes the typing, but the typist also noticed when an invoice looked wrong. If nothing replaces that, the diagram has moved the error rather than removed it.

## Worked example

`examples/faktury_as_is.json` is a small AS-IS in Polish — invoices arriving by email, manually re-typed, with a manager approval branch above a threshold. It generates `examples/faktury_as_is.bpmn`. It is deliberately unflattering: the re-typing step is the point, because that is what a TO-BE would target and what an automation business case would be built on.

## When a diagram is the wrong answer

A sequence of five steps with no decisions and no handovers is a numbered list, and drawing it wastes the reviewer's attention. BPMN earns its place when there are branches, parallel work, handovers between roles, or waiting on external events. If the description has none of those, say so and write the list.
