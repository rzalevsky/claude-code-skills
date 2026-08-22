---
name: process-automation-audit
description: Audit a business process BEFORE automating it — decide whether it is worth automating at all, whether it is stable enough to automate, what has to be fixed first, and where AI genuinely helps versus where plain rules are cheaper and more reliable. Produces a go / fix-first / no-go verdict with a payback estimate and named risks. Use this whenever someone proposes automating, digitising, or "putting AI on" a process; whenever they ask "should we automate this", "would an agent help here", "what's the ROI on this bot"; whenever an RPA, n8n, Power Automate, or LLM workflow is being scoped; and whenever an automation already exists and keeps breaking. Use it especially when the answer seems obviously yes — the expensive automation failures are the ones nobody questioned.
---

# Pre-automation process audit

Automating a bad process makes it a fast bad process, and now it is also harder to change. The purpose of this audit is to decide honestly whether to automate, and to catch the fixes that must happen first — before the tooling decision, which is where these conversations usually start.

The most valuable outcome of an audit is often "not yet, fix this first". That answer is unpopular and it is frequently correct.

## What to establish first

Do not accept a description of the process from someone who does not run it. The procedure and the practice diverge, and automation built on the procedure breaks on contact with the practice. Talk to the person doing the work, or watch it done once.

Six things, and none of them are optional:

1. **Volume** — how many times per week or month, and how that has moved over the last year. A trend downward is a reason not to automate at all.
2. **Handling time** — minutes per case, for the routine case and separately for the awkward one.
3. **Exception rate** — what share of cases deviate, and how many distinct kinds of deviation there are. This number decides everything downstream.
4. **Stability** — when did the rules last change, and what is scheduled to change. A process changing next quarter is not a candidate this quarter.
5. **Inputs** — what arrives, in what format, from whom, and how consistent it is. "PDF" is not an answer; "PDFs from 40 suppliers in 40 layouts, six of them scans" is.
6. **Who owns it** — who decides the rules, and who gets called when the automation is wrong at 7am. An automation without a named owner degrades quietly until it is switched off.

If you cannot get numbers, say so in the report rather than estimating them silently. "Volume unknown — the case rests on an assumption of ~200/month" is a usable finding; a fabricated number is not.

## The exception rate decides the shape

More than any other variable, the share of cases that deviate determines what to build:

| Exception rate | What it means |
|---|---|
| Under 5% | Straight-through automation is realistic. Route the rest to a human and stop there. |
| 5–20% | Automate the routine path only. Attempting the exceptions doubles the build and breaks first. |
| 20–50% | The process is not one process. Split it, and audit the parts separately — usually one part is clean and worth automating. |
| Over 50% | This is judgement work wearing a process costume. Automation will produce confident wrong answers. Support the human instead. |

A team that says "every case is different" is describing a process over 50%. Sometimes they are wrong and it is habit talking — check by sampling twenty real cases rather than arguing.

## Fix before automating

Some findings are prerequisites, not improvements. Automating over them locks the problem in place:

- **Steps that exist only to catch an earlier mistake.** Fix the earlier step; the check may disappear entirely.
- **Duplicate data entry.** Two systems that do not talk make an integration problem, not an automation problem, and the integration is usually cheaper.
- **Approvals nobody uses to decide anything.** If no approval has been refused in two years, it is a delay with a signature. Remove it before automating it.
- **Rules that live in one person's head.** They cannot be automated until they are written down, and writing them down often reveals they are inconsistent.
- **Inputs nobody controls.** If suppliers send whatever they like, either standardise the intake or accept that extraction accuracy is the ceiling on the whole project.

## Where AI belongs, and where it does not

This is the question people most want answered and most often get backwards. The useful split is not "hard versus easy" but **whether the correct output is determined by rules or by interpretation**.

**Plain rules are better** when the rule can be written down: thresholds, routing tables, format conversion, arithmetic, validation against a schema. Rules are cheap, deterministic, auditable, and they fail loudly. Putting a model on a task a regex handles adds cost, latency, and a failure mode that looks like success.

**A model earns its place** when the input is unstructured and variable — extracting fields from documents in layouts you have not seen, classifying free text, matching things phrased differently, drafting text a human will review. All of these share a property: a human could do them but could not write down the rule.

**Nothing should be automated at all** when the decision needs accountability the automation cannot carry — anything where being wrong is expensive and the wrongness is not detectable downstream.

The load-bearing question for any AI step: **how will you know when it is wrong?** If the answer is "the model is usually right", that is not a control. Real answers look like: validation against a schema that stops the run, a checksum, a cross-check against a second source, a human reviewing a sample, a confidence threshold that routes to a person. If no answer exists, do not put a model there — put a rule there and accept a narrower scope.

## Is it worth it

A rough payback beats a precise one nobody believes:

```
annual hours saved = cases/year × minutes saved per case ÷ 60
annual value       = annual hours saved × fully loaded hourly cost
payback (months)   = build cost ÷ (annual value ÷ 12)
```

Then subtract the things people leave out, because they are what turns a six-month payback into an eighteen-month one:

- **Maintenance** — assume 15–25% of build cost per year. Interfaces change, suppliers change formats, the rules move.
- **Exception handling** — the cases the automation rejects still take human time, and often *more* time per case than before, because the easy ones are gone and the person has lost the routine.
- **Rebuild risk** — if the underlying system is being replaced within two years, most of the build is written off.

State the payback as a range with the assumptions visible. "8–14 months, assuming 200 cases/month and 12 minutes saved each" invites correction; "11.3 months" invites belief.

Below roughly 30 minutes saved per week, the honest answer is usually no. The time is real but it is smaller than the cost of owning one more thing that can break.

## Report format

Keep the whole thing to one page. Anything longer will be skimmed for the verdict, so lead with it.

```
VERDICT: GO | FIX FIRST | NO-GO

Process:        [name, owner, systems involved]
Volume:         [cases/period] · Handling time: [min/case] · Exceptions: [%]
Time saved:     [hours/year] · Payback: [range, months]

FIX BEFORE AUTOMATING
1. [what, why it blocks, who owns the fix]

AUTOMATE
[what specifically, with which approach and why — rules or model]

LEAVE MANUAL
[what stays with a person, and why that is the right call]

HOW YOU WILL KNOW IT IS WRONG
[the control on each automated step — validation, threshold, sampling, cross-check]

RISKS
[named, with what would trigger them]

ASSUMPTIONS
[every number you were given versus every number you estimated]
```

The last two sections are what make the report usable six months later, when someone asks why the automation was scoped that way. `references/scoring.md` has the interview questions worth asking verbatim, a worked Polish example, and the numbers behind the exception-rate table.
