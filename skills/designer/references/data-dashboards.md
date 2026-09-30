# Dashboards, admin panels, data interfaces

The main question of a dashboard: **"does anything need my attention right now,
and what should I do?"** Everything else is secondary. A screen that simply
shows every number fails at the main job.

## Contents
1. Screen hierarchy · 2. Metrics (KPIs) · 3. Tables · 4. Charts ·
5. Status and alerts · 6. Live data · 7. Controls and dangerous actions ·
8. Money and numbers · 9. Density

## 1. Screen hierarchy
- Top to bottom by importance for the decision: **system state and alarms →
  key metrics → what can or must be worked on (orders, jobs, tasks) →
  history and details.**
- An alarm about a problem (stopped, stale data, a safeguard triggered) is
  always at the top and the most prominent thing; the normal state is calm and
  compact ("Running").
- Do not show a metric nobody makes decisions on. Ask of every element:
  "what action will it change?"

## 2. Metrics (KPIs)
- A large number with a short caption under it (not the other way round); the
  unit right next to it; the period obvious ("today").
- Show change with a sign, an arrow and color at once (▲ +1.2% / ▼ −0.8%),
  never color alone.
- 3-6 metrics in the first row; more, group or remove. Equal card heights and
  a shared value baseline (`align-content: start`).
- A comparison to a reference (limit, yesterday, target) beats a lone number:
  "error rate 1.2% of a 5% budget".

## 3. Tables
- Columns: identifier (name) first, then the important values, actions last.
  Anything that does not help a decision is removed or moved into an expander.
- Numbers right-aligned, `tabular-nums`, the same number of decimals within a
  column; the unit in the header. Text left-aligned.
- Sticky header, sorting on important columns (with an indicator), filter/
  search for long lists, sensible row height (32-48 px).
- Separate rows with a thin line or light zebra striping, not both. No
  vertical lines unless they help reading.
- An empty table explains what it is and how data will appear. Loading is
  skeleton rows.
- A row action is a visible button or a "⋯" menu with a label (`aria-label`),
  not hidden behind hover only.

## 4. Charts
- Type follows the question: **trend** → line/area; **comparison** → bars;
  **share of a whole** → 100% stacked bar (pie only for 2-4 parts);
  **distribution** → histogram; **relationship** → scatter plot.
- Bars start at zero; a line may not, but mark it. No 3D and no dual axes
  unless absolutely necessary.
- Label directly on lines/bars instead of a legend; at most 5-6 series; colors
  distinguishable under color blindness and also distinguished by shape or
  label.
- A time axis with a clear unit; thresholds/limits as a labeled line; events
  (entry, exit) as markers.
- Always provide a value on hover **and** an accessible alternative (a data
  table or a text summary).
- An honest "No data for this period" beats an empty frame.

## 5. Status and alerts
- Status is a word + color + optionally an icon: "Running", "Stopped", "No
  connection". Color only by meaning (green: normal, yellow: attention, red:
  action required).
- Levels: critical is a prominent banner at the top that stays until
  resolved; a warning sits next to the affected area; info is unobtrusive.
  Toasts only for confirming simple actions, never for anything important.
- A message = what happened + how it affects you + what to do.
- Do not shout about trivia: if everything is red, red means nothing.

## 6. Live data
- Update **in place**: do not redraw the whole screen, do not reset scroll,
  selection, expanded blocks and focus. Do not reorder rows under the user's
  finger.
- Show **freshness**: "updated 12:04:31" / "data 40 s old". Mark stale data
  explicitly and never pass it off as current.
- Do not animate every update; if a change matters, highlight it softly and
  briefly (<= 1 s).
- Refresh rate follows the pace of decisions, not "as often as possible"; on a
  network error keep the last value with a note, do not zero it out.
- Let the user pause updates while they study the data.
- A long-lived warning (paused processing, "no connection", sync error) shows **when
  it started**: "Enabled 17 Sep 20:39 (2 days ago)". Without that, a two-day-old
  forgotten block looks the same as a fresh one, and the person does not
  realize it is not today's failure.
- If the system can recover on its own, say so in the warning ("Clears itself
  once the connection is stable") and separately say what to do manually if
  self-recovery is not working (the worker is not running).

## 7. Controls and dangerous actions
- Separate **observing** from **controlling**. Control buttons are compact, in
  a dedicated place, not among the metrics.
- Actions with different consequences get different buttons and keys: "close
  panel" ≠ "stop the system" ≠ "emergency stop".
- A dangerous action: a confirmation that **names the action and its
  consequence** ("Stop the worker? Jobs already running will finish; queued
  jobs wait"). Cheap protection against accidental keypresses: "press twice
  within N seconds" with an on-screen hint.
- Actions that only raise safety (pause, "stop") should be easier to reach than
  actions that remove protection (start, clear a block); the latter may be
  required to go through a deliberate, separate path.
- After an action, a clear result: what happened and what the state is now.

## 8. Money and numbers
- Format by locale (`Intl.NumberFormat`): "1,234.56" or "1 234,56"; non-
  breaking spaces; the currency unit next to the value ("EUR", "$"); the same
  number of decimals for one quantity (price and amount differ, so do not force
  them to match).
- Do not show 8 decimals when 2 are significant; but do not round where
  precision matters (fees, small amounts), following the rules of each
  quantity.
- Negatives with "−" (U+2212) and a sign, positive changes with "+"; ▲/▼
  supplement color.
- Percent and absolute side by side ("+12.40 EUR · +1.01%").
- Timestamps in the user's time zone, in one format; for "recent", relative
  time with the exact value on hover.

## 9. Density
- An expert who watches constantly benefits from density, but only with strict
  alignment and hierarchy; otherwise density turns into noise.
- Tune density with spacing and size, not by shrinking text below 14 px. One
  screen, one density.
- Do not cram "everything on one screen" at any cost: a second screen/tab for
  details beats an overloaded first one.
