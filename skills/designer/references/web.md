# Web: sites, landing pages, web apps

## Contents
1. Stack and reuse · 2. Semantics · 3. CSS · 4. Responsiveness · 5. Forms ·
6. Tables · 7. Theme, color, motion · 8. Images and speed · 9. Complex widgets ·
10. Landing pages · 11. Single-file static page

## 1. Stack and reuse
- Start with what the project already has (React/Vue/Svelte/templates, CSS
  framework, components). Never mix two styling systems.
- No framework and a small task: plain HTML + CSS (+ a little JS). Keep state
  minimal; extra state is a bug source.
- Tokens are CSS variables (`assets/tokens.css`) or the existing framework's
  theme; do not introduce values outside the scale.

## 2. Semantics (the basis of accessibility and "free" robustness)
- Landmarks: `<header>`, `<nav>`, `<main>` (exactly one), `<footer>`; a "skip to
  content" link first.
- `<button>` for an action on the page; `<a href>` for navigation. No
  `<div onclick>`.
- Headings in order (one `h1`, then `h2`, `h3` with no gaps). The level
  describes structure, not font size (CSS sets the size).
- Lists are `<ul>/<ol>`, data is `<table>` with `<th scope>`, field captions
  are `<label for>`. Images get `alt` (empty for decorative ones).
- ARIA only to supplement native semantics (`aria-describedby` for an error,
  `role="status"` for a status, `aria-current="page"` in navigation).

## 3. CSS
- Units: `rem` for fonts and spacing (respects user settings), `%`/`fr`/
  `min()`/`max()`/`clamp()` for sizes; `px` for borders and shadows.
- Layout: `grid` for two dimensions, `flex` for one; `gap` instead of outer
  margins. Auto columns: `repeat(auto-fit, minmax(min(100%, 16rem), 1fr))`.
- Do not fix `height`; use `min-height`. Do not set widths on buttons and
  headings; translated strings are often longer than English.
- Logical properties (`margin-inline`, `padding-block`, `inset-inline-start`)
  are RTL-ready from the start.
- Focus: `:focus-visible` with a clearly visible outline; `outline: none`
  without a replacement is not allowed.
- Fluid heading size: `clamp(1.5rem, 1.1rem + 1.6vw, 2.25rem)`.
- Keep specificity low: classes, no `!important` (exception:
  `prefers-reduced-motion`).

## 4. Responsiveness
- Mobile-first: base styles for narrow screens, `@media (min-width: …)` adds
  to them.
- Breakpoints follow the content ("it breaks, add one"), typically around 640 /
  768 / 1024 / 1280 px. Container: `max-width: 72rem; margin-inline: auto`.
- Check 375 / 768 / 1280 and a wide screen. The page must not scroll
  horizontally.
- A table on a narrow screen: either scroll inside its own container
  (`overflow-x: auto`, with a visible hint there is more) or reflow rows into
  "list cards" with field labels.
- Touch: targets >= 44 px with gaps between them; hover is never the only way
  to reveal something (`@media (hover: hover)`).

## 5. Forms
- A visible `<label>`; hint via `aria-describedby`; error as text next to the
  field, `aria-invalid="true"`, and a reference to it in `aria-describedby`.
- Correct `type` (`email`, `tel`, `number` with care, `url`),
  `inputmode="decimal|numeric"`, `autocomplete`. For money, usually
  `inputmode="decimal"` + `type="text"`.
- Validate on leaving a field and on submit; after a failed submit the data
  stays; focus moves to the first invalid field (or to an error summary).
- Submit button: while in progress, "Saving…" and block repeat submission;
  after success, a clear confirmation.
- A single column of fields reads and fills better than several.

## 6. Tables
- Numbers right-aligned with `font-variant-numeric: tabular-nums`; units in
  the column header, not in every cell.
- Sticky header for long tables; sorting with a visible indicator and
  `aria-sort`; the row header is `<th scope="row">`.
- Truncate long values with the full text in `title`/an expander rather than
  breaking the layout.

## 7. Theme, color, motion
- `color-scheme: light dark` + `light-dark()` tokens; a manual switch via
  `<html data-theme>`, with the choice persisted (`localStorage`, inside
  `try/catch`).
- Motion 120-250 ms, `ease-out`; nothing that gets in the way of work; under
  `prefers-reduced-motion: reduce` remove everything except what is essential.

## 8. Images and speed
- `width`/`height` on images (no layout shift), `loading="lazy"` below the
  fold, `srcset`/`sizes` for large ones, modern formats.
- System font stack by default (fast, broad script coverage); at most one web
  font, with `font-display: swap` and a check that it covers the scripts you
  need.
- Show loading data as a skeleton of the right size.

## 9. Complex widgets
Dialog, dropdown menu, combobox, tabs, tooltip, calendar: focus traps, roles
and keyboard support are hard to get right by hand. Use a proven library
(Radix, Headless UI, React Aria, native `<dialog>`/`popover`) instead of
writing your own.

## 10. Landing and marketing pages
- The first screen answers three questions: **what is this**, **who is it for
  / how does it help**, **what to do next**, with one primary call to action.
- Then one section per idea; rhythm: a headline that states the takeaway → a
  short explanation → proof (numbers, testimonials, a product screenshot).
- A real product screenshot or demo is more convincing than an abstract
  illustration.
- Do not overload the navigation; repeat the call to action at the end.
- Copy: short paragraphs, specifics instead of "innovative solution".

## 11. Single-file static page
One `.html`: `<meta charset>`, `<meta name="viewport">`, `lang` set to the
page language, `<title>`, styles in `<style>` (tokens at the top), no external
dependencies. If it will be published as an artifact, follow that platform's
rules (CDN allow-list, theme, responsiveness, no external requests) and load
a matching artifact-design skill if one is available.
