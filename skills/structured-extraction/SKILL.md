---
name: structured-extraction
description: Extract fields from unstructured documents — invoices, emails, forms, contracts, reports — into a strict schema, with validation that stops the run instead of writing a doubtful value into a system of record. Covers schema design, prompting for extraction, the locale traps that silently corrupt numbers and dates, and what to do on failure. Use this whenever someone wants data pulled out of documents into a spreadsheet, database, or API; whenever an LLM is asked to "return JSON" that something downstream will consume; whenever an extraction pipeline is producing wrong values; and whenever you are wiring document intake into n8n, Make, Power Automate, or a custom script. Use it especially when the extracted data feeds accounting, billing, or anything else where a silently wrong number is worse than a visible failure.
---

# Structured extraction that fails loudly

The dangerous failure in document extraction is not the crash. It is the invoice booked at 123.00 zł when it said 123,45 — a plausible number, in the right field, wrong. Nobody notices for a month, and by then the source email is buried.

So the design principle throughout: **a doubtful value must never reach the system of record.** Getting nothing and knowing it is recoverable in minutes; getting something wrong and not knowing is not.

## Design the schema before the prompt

The schema is the contract. Write it first, and keep it strict — the point of a schema is to reject things.

```json
{
  "type": "object",
  "required": ["counterparty", "amount", "currency", "due_date", "invoice_number"],
  "additionalProperties": false,
  "properties": {
    "counterparty":   {"type": "string", "minLength": 2},
    "amount":         {"type": "number", "exclusiveMinimum": 0},
    "currency":       {"type": "string", "enum": ["PLN", "EUR", "USD"]},
    "due_date":       {"type": "string", "format": "date"},
    "invoice_number": {"type": "string", "minLength": 1}
  }
}
```

Three decisions in that snippet carry most of the weight:

- **`additionalProperties: false`** — a model that invents a field is a model that misread the document. Catch it here rather than wondering later where `vat_rate` came from.
- **Enums wherever the value set is closed** — currencies, categories, statuses. An enum turns a hallucination into a validation error.
- **Numbers typed as numbers, not strings** — pushing the parse into validation is what catches the comma-decimal case below.

**Model "absent" explicitly.** Every optional field needs a defined representation for "not in the document" — `null`, not an empty string, and never a guess. Say so in the prompt: *if a field is not present, return null; do not infer it.* Without that instruction the model will fill the gap plausibly, and a plausible invented due date is the worst possible output.

## The traps that corrupt data silently

These are ordinary, they show up in real documents, and each one produces a wrong value rather than an error.

**Decimal comma.** A Polish- or German-language document says `1 234,56`. A model trained on that text returns `1234,56`, and `float("1234,56")` throws — or worse, upstream code splits on the comma and books `1234`. Normalise explicitly: strip spaces and non-breaking spaces used as thousands separators, then convert the decimal comma. Then check the result is still plausibly the same magnitude as the source string.

**Ambiguous dates.** `03/04/2026` is 3 April in Warsaw and 4 March in Chicago. Never let the model decide: require ISO `YYYY-MM-DD` output, and where the source is genuinely ambiguous, prefer failing over guessing. If the document locale is known, state it in the prompt.

**Thousands separators.** `1.234,56` and `1,234.56` are the same amount under different conventions. A parser that handles one silently mangles the other.

**Multi-page and multi-item documents.** An invoice with three line items has one total and three amounts. Say in the schema and the prompt which one you want, or you will get whichever the model saw last.

**Currency inferred from the language.** A Polish invoice can be denominated in EUR. Extract the currency from the document; never derive it from the document's language.

**Look-alike characters.** `О` (Cyrillic) and `O` (Latin) in an invoice number are different strings that render identically. If invoice numbers are matching keys downstream, normalise them.

## Validation is a separate step

Keep validation out of the extraction call. A model asked to extract *and* verify will tell you it verified. Validate in code that has no incentive to be optimistic.

```bash
python3 scripts/validate_extraction.py --schema schema.json --data extracted.json
python3 scripts/validate_extraction.py --schema schema.json --data extracted.json --normalise
```

The bundled script checks the schema, applies locale normalisation for numbers and dates, and — critically — **exits non-zero on any failure with the raw input attached**, so the workflow step around it fails rather than passing a partial record downstream.

`examples/invoice.schema.json` is a working schema for invoice intake — the five fields, the currency enum, `additionalProperties: false`, and one nullable optional field. Use it as the starting shape rather than writing a schema from scratch; the decisions in it are the ones that matter.

Checks worth adding beyond the schema, because they catch the errors a schema cannot:

- **Cross-field arithmetic** — do the line items sum to the total? This single check catches most extraction errors on invoices, because a misread digit rarely survives it.
- **Range plausibility** — an amount three orders of magnitude off the usual for this supplier is worth a human look even when it parses.
- **Date sanity** — a due date before the issue date, or five years out, is a misread rather than an unusual invoice.
- **Round-trip on identifiers** — does the extracted invoice number appear verbatim in the source text? If not, the model reformatted it.

## What to do when validation fails

**Fail the run, attach the raw model output, and stop.** Do not retry silently, do not write a partial record, do not substitute a default.

That last point is worth being blunt about: defaults are how bad data gets in. A missing `due_date` filled with today's date produces a row that looks complete and is wrong, and no downstream check will ever flag it. A failed run produces an alert somebody handles.

Two exceptions worth building deliberately:

- **One retry with a lower temperature** when the failure is a format error rather than a content error — invalid JSON, a wrapped code fence. Retry the parse, not the judgement.
- **Route to a human queue** when the document is simply hard — a scan, a layout never seen before. Making a person handle 15% of cases is a working system; making a model guess on that 15% is not.

## Running the model

- **Temperature 0.** Extraction is not a creative task.
- **Local models are viable and often correct** for extraction. A 7B instruct model handles invoice fields well, and running locally means the data — counterparty names, amounts, payment terms — never leaves the network. For anything covered by GDPR or a client NDA, that is the deciding argument rather than a nice-to-have.
- **Ask for JSON only, and strip fences anyway.** Models wrap output in ```json fences regardless of instructions. Handle it in code rather than in the prompt.
- **Put the schema in the prompt verbatim.** Describing the shape in prose produces near-miss field names.
- **One document per call.** Batching saves tokens and costs accuracy on exactly the documents you would rather get right.

## Where this came from

The failure mode this skill is built around — validation that throws with the raw model output attached rather than writing a doubtful value — comes from a working n8n invoice intake workflow running on a local model: [github.com/rzalevsky/n8n-automation-workflows](https://github.com/rzalevsky/n8n-automation-workflows). The comma-decimal case is in there because a Polish-trained model returned `123,45` on the second day of running it.
