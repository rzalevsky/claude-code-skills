# BPMN cases that are easy to get wrong

Read this when the process has loops, waiting, more than one organisation, or has grown large enough that someone suggests a subprocess.

## Loops and rework

Rework is the most common thing missing from a first-pass description, because people describe processes as if approvals succeed.

Model a rejection as a sequence flow back to the step that has to be redone — not as a separate "correct the invoice" branch that quietly rejoins later. The loop is the honest shape: it shows the work can be done twice, and if a diagram shows a loop, somebody will eventually ask how often it is taken. That question is usually where the automation case is.

```
t_wprowadz -> g_kontrola -> (nie) -> t_wprowadz     loop back to the same task
                         -> (tak) -> t_zatwierdz
```

The layout script routes a backward flow under both elements so it reads as a loop rather than crossing the diagram.

Guard against infinite loops in the description, not in the notation: ask what happens on the third rejection. There is almost always an escalation that nobody mentioned.

## Waiting

There is a real difference between a step that takes time and a step that waits.

- **Takes time** — a task. "Kontrola dokumentu, 20 minut."
- **Waits for something external** — `intermediateCatchEvent`. Waiting for a supplier reply, a bank confirmation, the first of the month.

The distinction matters because waiting is where processes actually lose days, and a model that hides waiting inside tasks makes a two-week process look like four hours of work. When someone says "then we wait for the client", that is an event, and its duration belongs on the diagram.

For a deadline with an escalation, attach a timer boundary event to the task and route it to whatever happens when time runs out. If the tooling in play does not support boundary events cleanly, an `intermediateCatchEvent` after an exclusive gateway is an acceptable simplification — say in the notes that it is one.

## More than one organisation

Lanes are roles inside *one* process, under one owner. A supplier, a client, or a bank is a separate participant: their internal steps are none of your process's business, and modelling them as a lane implies control that does not exist.

- Same organisation, different roles → lanes in one pool.
- Different organisations → separate pools, connected by message flows, with the other party's internals left as a black box.

The practical tell: if you cannot say who would change the step if it were wrong, it does not belong in your pool.

## Subprocesses

A subprocess earns its place when a block of steps is genuinely reusable, or when collapsing it makes the main flow readable at a glance. It does not earn its place merely because the diagram got long.

Bad reason: "the model has 30 elements and looks crowded." A crowded diagram usually means the scope is wrong — the model covers two processes that happen to run one after the other. Split by process, not by page.

Good reason: "the approval sequence is identical in four processes." Then it is one subprocess with one owner, and updating it updates all four.

## Data and documents

Data objects clarify, so use them where the artefact is the point of contention — the spreadsheet that gets emailed, the PDF that gets re-typed, the form that exists in three versions. Do not attach a data object to every task; a diagram where every step touches a document teaches nothing.

Where a document sits *between* steps is usually more informative than the step itself. "Faktura leży w skrzynce do poniedziałku" is a queue, and queues are where processes lose time.

## Naming

Names are what make a model reviewable by the person who owns the process.

- Tasks: verb + object — "Wprowadzenie faktury do systemu", not "Faktura" or "Wprowadzanie".
- Gateways: a question — "Kwota > 5000 zł?", not "Kwota".
- Events: a state that has been reached — "Faktura zaksięgowana", not "Koniec".
- Flows out of an exclusive gateway: the condition — "tak" / "nie" when the gateway asks a yes/no question, otherwise the actual condition.

Keep names in the language the process is run in. A Polish accounting process modelled with English task names will be reviewed by people who then have to translate back, and translation loses exactly the specifics you were trying to capture.

## A quick self-check before handing over the model

- Every gateway asks a question, and every branch out of it is labelled.
- Every end event names an outcome, and different outcomes have different end events.
- Every lane is a role someone actually holds.
- The exceptions are on the diagram, not in a footnote.
- Every assumption you had to make is written down next to the model.
- Somebody who runs this process daily would recognise it — including the parts that are annoying.
