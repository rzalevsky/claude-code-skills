# Interview questions and a worked example

## Questions that get real answers

The difference between a useful audit and a wasted afternoon is whether the questions are specific enough to answer. General questions get general answers, and general answers cannot be modelled.

**Volume and time**

- "How many of these did you handle last week?" — not "how many per month, on average". People count weeks accurately and average months badly.
- "How long does a normal one take, start to finish?" then separately "and the worst one you had recently?"
- "Is this more or less than a year ago?"

**Exceptions — the most important part**

- "Walk me through the last one that went wrong."
- "What makes you stop and ask someone?"
- "Of last week's cases, how many were completely routine?"
- "What arrives that you have to fix before you can start?"

That last question surfaces input-quality problems, which are the most common cause of automation projects overrunning. If the answer involves regularly phoning a supplier to ask what a document means, extraction accuracy has a ceiling no model raises.

**Stability**

- "When did the rules last change?"
- "Is anything changing in this area in the next six months?"
- "Who would tell you if the rules changed?"

If nobody would tell them, the automation will silently run on outdated rules — worth naming as a risk in the report.

**Ownership**

- "Who decides how this should work?"
- "If this ran automatically and produced something wrong at 7am, who gets the call?"
- "Who would notice it was wrong?"

The third question is the one that matters. A process where nobody would notice a wrong output for a week is a process where automation errors compound before anyone reacts.

## Why the exception-rate thresholds sit where they do

The numbers in the main table are not from a study — they come from a simple observation about build cost, and it is worth being open about that.

Handling an exception path costs roughly as much to build as the happy path, because it needs its own detection, its own routing, and its own tests. So the build cost of covering exceptions scales with *how many kinds* there are, while the benefit scales with *how frequent* they are. Under 5%, the exceptions are rare enough that routing them to a person costs almost nothing. Above 20%, the exception handling dominates the build and the automation ends up more complex than the process it replaced.

The 50% line is different in kind. Above it, the "process" is a set of decisions someone makes case by case using judgement they cannot fully articulate. Automation there does not fail visibly — it produces confident, plausible, wrong output, which is worse than no automation, because the wrongness is now invisible.

## Worked example: faktury przychodzące

**What was described.** Invoices arrive by email. Accounting downloads the attachment, types the counterparty, amount, currency, due date and invoice number into a spreadsheet, and books it. Over 5000 zł it goes to a manager for approval first.

**What the numbers showed.** ~180 invoices/month. 6–8 minutes each for a routine one, up to 25 when something is unclear. Roughly 15% needed a phone call — missing PO number, an unfamiliar supplier, an amount that did not match the order. Rules unchanged for two years. Around 40 suppliers, about 6 of whom send scans rather than digital PDFs.

**Verdict: FIX FIRST, then automate the routine path.**

*Fix before automating.* The approval threshold sat at 5000 zł and had not been reviewed in years; over the sampled quarter no approval above it had been refused. Automating that approval would have automated a delay. Recommendation: review the threshold with the process owner first — either raise it to where refusals actually happen, or drop the step.

*Automate.* Field extraction into a strict schema (counterparty, amount, currency, due date, invoice number), with validation that stops the run rather than writing a doubtful value. This is the part where a model earns its place: 40 supplier layouts is exactly the case where the rule cannot be written down. The subsequent steps — threshold check, spreadsheet row, alert above a limit — are plain rules and should stay rules.

*Leave manual.* The 6 suppliers sending scans, and everything the validation rejects. Scans need OCR, OCR errors are silent, and the volume does not justify solving it.

*How you will know it is wrong.* Every extracted record is validated before it is written: required fields present, amount parses as a number, currency in an allow-list, due date a real date not in the distant past. On failure the run throws with the raw model output attached, so the failure is visible and diagnosable rather than a wrong number in the accounts. One specific trap worth encoding: a Polish-language model will return `123,45` where the schema expects `123.45`, and a naive float conversion turns that into either a crash or, worse, a silently truncated number.

*Numbers.* ~180/month × 5 minutes saved ≈ 15 hours/month ≈ 180 hours/year. Payback in the region of 6–10 months depending on build cost, before maintenance at ~20%/year. The 15% exception rate stays human either way — the saving comes from the 85%, and the report should say so rather than quietly counting all 180.

**What made this a fix-first rather than a go.** Not the technology. The approval step that no longer decided anything, and the input quality problem with the scanned invoices. Both would have been automated into permanence.

## Failure patterns worth recognising early

- **Automating the measurement instead of the work.** A dashboard showing how slow the process is does not make it faster, and it is easier to build, so it often gets built first.
- **The pilot that stays a pilot.** Nobody agreed who owns it in production, so it runs on one person's laptop until they change jobs.
- **The 100% ambition.** The last 10% of cases costs more than the first 90% and is where the accuracy problems live. Scope for the 90% deliberately, not apologetically.
- **The undocumented rule discovered mid-build.** Surfaces as "oh, we also always do X for that client". This is why the sample of twenty real cases beats any interview.
- **A model where a regex would do.** Costs more, runs slower, and fails in a way that looks like it worked.
