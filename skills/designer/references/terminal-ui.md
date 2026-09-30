# Terminal interfaces: TUI and CLI

## Contents
1. Tooling · 2. Screen and layout · 3. Color and symbols · 4. Keys ·
5. Dangerous actions · 6. Refresh and performance · 7. CLI output ·
8. Errors and exit codes · 9. Verification · 10. Textual and Rich pitfalls

## 1. Tooling
Use what the project already has: Python: Textual (interactive TUI) and Rich
(nice output); Node: Ink, blessed; Go: Bubble Tea; Rust: ratatui. Textual
provides widgets (tables, inputs, a footer with key hints), CSS-like styling,
periodic refresh (`set_interval`) and a test mode (`run_test`).

## 2. Screen and layout
- Think in **cells**. The minimum is **80×24**: the interface must be usable
  in such a terminal; in a wide one it uses the space instead of stretching.
- React to resizing. Do not rely on a fixed width.
- Regions: the top line is name and status; the center is working data; the
  bottom is key hints and status messages. Anything safety-relevant (mode,
  paused processing, "no connection") is always visible.
- Build hierarchy with bold/dim/color and spacing, not an abundance of
  borders. Borders and separators sparingly and in one style.
- Tables: numbers right-aligned, units in headers, truncation with "…" (the
  full value in a details view), selection with arrow keys.
- Unicode symbols: the width of "wide" characters and emoji in terminals is
  unpredictable. For alignment use simple ones (▲ ▼ ● ✓ ✗ —, and test in the
  target terminal); avoid emoji.

## 3. Color and symbols
- Colors are **semantic** and from the base 16 ANSI colors (so any terminal
  theme works). Do not set a background everywhere: let the terminal stay
  itself.
- Check legibility in both dark and light terminal themes; avoid "bright
  yellow on white" and "dark blue on black".
- **Not color alone**: status = color + a word/symbol ("● running", "✗
  stopped", "▲ +1.2", "▼ −0.8").
- Honor `NO_COLOR` and the absence of a TTY: when output goes to a pipe/file,
  plain text with no colors or control codes; for machines, a `--json` flag.

## 4. Keys
- Key hints are always visible at the bottom (in Textual, `Footer`); `?` opens
  full help.
- Familiar conventions: `q` quits a screen/viewer, `Esc` goes back/closes,
  `Enter` selects/confirms, arrows and `j/k` move, `/` searches, `Tab` goes to
  the next element, `Ctrl+C` always interrupts and never gets swallowed.
- Keys are predictable and are not rebound between screens without reason.
- Dangerous keys are not next to frequent ones (do not put "stop" next to
  "refresh").

## 5. Dangerous actions
- Distinguish **quitting the interface** (does not affect the system) from
  **stopping the system** (does). Different keys, different labels,
  confirmation only on the second.
- Confirmation: either "press again within 5-6 s" with a hint such as "Press s
  again to stop", or typing a word. One accidental keypress does nothing
  irreversible.
- Actions that remove protection do not get a single key; keep them a
  deliberate separate path (a command with explicit confirmation).
- A graceful stop is preferable to a hard one: send a proper signal (SIGTERM)
  and show "stopping…"; do not add a hidden forced SIGKILL.
- If the action is impossible (the process is not running), say so instead of
  crashing.

## 6. Refresh and performance
- Update **in place**; do not redraw the whole screen on a timer (flicker,
  lost selection). Preserve cursor/selection/scroll when data updates.
- Interval follows the pace of decisions (usually 1-5 s). Network calls run
  off the render path (asynchronously), with a timeout; on error keep the
  previous data marked "no connection", do not crash.
- Show the time of the last update.

## 7. CLI output (non-interactive)
- The useful thing first: the result or status; details behind `-v`.
- Aligned tables; output that suits both the eye and `grep`; for scripts,
  `--json` with stable keys.
- `--help` with usage examples; subcommands with short descriptions.
- Long operations: a spinner/progress (>1 s), with an estimate of time left
  if known; no animation in a pipe.
- Confirmation for dangerous commands (`--yes` for scripts, an interactive
  question for people).

## 8. Errors and exit codes
- A message: **what happened + why (if known) + what to do**. No stack trace
  for ordinary user errors; the trace goes behind `-v`/into a log.
- Exit codes: 0 for success, non-zero for errors; distinguish "incorrect
  usage" (2) from "refused by a condition" (for example, 3).
- Errors go to stderr, results to stdout.

## 9. Verification
- Textual: `async with app.run_test(size=(80, 24)) as pilot:` — press keys via
  `pilot.press(...)`, check widget state; `app.export_screenshot()` → SVG →
  `scripts/shots.sh file.svg <dir>` (from this skill's folder) → PNG you can open
  with `Read` and actually look at.
- Check at least 80×24 and a wide size (for example 160×40), dark and light
  terminal themes, no color (`NO_COLOR=1`), empty data and a network error.
- Walk through the main scenario and the "dangerous action" scenario by key.

## 10. Textual and Rich pitfalls (learned in practice)
- **Always escape foreign text.** Anything that did not come from you (news
  headlines, error reasons, symbol names, API responses, command output) goes
  through `textual.markup.escape` (for Rich, `rich.markup.escape`) before it
  reaches a markup-enabled widget. Otherwise a string like
  `[@click=app.quit]x[/]` turns into a live action link, and `[red]` breaks
  coloring. Add a test with such a string everywhere external text lands.
- **Measure theme colors, do not guess.** Take the actual values from the
  theme (`app.theme_variables` / `app.current_theme`) and compute WCAG
  contrast for every "text on background" pair. Built-in pairs can fall below
  4.5:1: in one case red `$error` on a dark surface measured 3.44:1, and the
  readable variant was lighter (`$error-lighten-2`). Check both themes.
- **Variable names depend on the Textual version.** In one version
  `$text-muted` did not dim the text, and the variable that did was
  `$foreground-muted`. If a variable "does not work", it is not always a bug:
  compare on a screenshot whether the muted text is really muted.
- **Check 80×24 with your eyes.** With 80 columns the key footer gets cut in
  the middle of a hint: shorten the labels and put important keys first.
  Block characters for gauges (▁▂▃▅) look different in different fonts: for a
  "bar" use even full blocks and judge the result on a screenshot.
- **Height is currency.** A dangerous-action confirmation and warnings must
  not push data out: the confirmation line is 1-2 lines; collapse identical
  warnings into one; do not show the same news both in the status line and in
  the warnings block.
- **Invisible characters in code.** Auto-formatters (ruff and others) may
  replace `" "` and `"−"` with the actual characters, which are
  invisible in an editor. Keep NBSP and the minus sign as named constants with
  a comment, and cover the number formatter with a test that fails if they are
  swapped for a plain space/hyphen.
- **The interface is a separate process from the system.** A dashboard that
  only reads state must not be able to change it quietly: actions only via
  explicit keys with confirmation, and "close the dashboard" never stops the
  worker.
