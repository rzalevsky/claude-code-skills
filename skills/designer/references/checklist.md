# UI review checklist

Use it in step 7 (verification) and in mode B (audit). Every item is checkable:
yes/no, not "looks roughly fine". Skip what does not apply to the platform.

## Contents
1. Tasks and hierarchy · 2. Layout and spacing · 3. Typography · 4. Color and
contrast · 5. Components and states · 6. Forms · 7. Navigation and keyboard ·
8. Accessibility · 9. Responsiveness · 10. Copy and locale · 11. Speed ·
12. Template mistakes

## 1. Tasks and hierarchy
- [ ] You can name the screen's **one main** action or message, and it is more
      prominent than everything else.
- [ ] The user's main task takes the minimum number of steps, and you walked
      through it yourself rather than only looking at a picture.
- [ ] Everything that does not help the main task is removed or hidden.
- [ ] No duplicates: the same information is not repeated in three places.
- [ ] Block order matches importance for the decision, not the order of fields
      in the database.

## 2. Layout and spacing
- [ ] All spacing and sizes come from the scale (multiples of 4 px / tokens);
      no "13 px".
- [ ] Related things are grouped closer than unrelated ones (spacing inside a
      group is smaller than between groups).
- [ ] Alignment on shared axes: block edges, captions and values do not drift
      (check neighboring cards: values on one line).
- [ ] Reading line length <= ~65-75 characters.
- [ ] Numbers in columns are aligned by digit (`tabular-nums`, right-aligned).
- [ ] No clipped, overlapping or overflowing content.
- [ ] Just enough borders and shadows for grouping to read; "everything in
      cards" is not acceptable.

## 3. Typography
- [ ] <= 2 font families; 4-5 sizes across the product; 2-3 weights.
- [ ] Body text >= 16 px (14 px acceptable for dense tables/captions); no
      small light-gray text for anything important.
- [ ] Line height ~1.4-1.6 for text, ~1.2 for headings.
- [ ] Headings follow levels with no gaps (h1 → h2 → h3).
- [ ] The font covers the scripts the interface uses (no "tofu" boxes and no
      fallback to another font mid-word).
- [ ] Bold is used rarely and deliberately.

## 4. Color and contrast
- [ ] Normal text >= 4.5:1, large (>= 24 px or >= 19 px bold) >= 3:1, field
      borders/icons/indicators >= 3:1, in **both** themes.
- [ ] Contrast is **computed**, not judged by eye (in a TUI from the theme
      values, on the web from the tokens); red/yellow text on a dark
      background is a frequent failure.
- [ ] One accent color; semantic colors (success, warning, error, info) are
      used only by meaning.
- [ ] Meaning is not conveyed by color alone: a sign ("+"/"−"), arrow, icon or
      word alongside.
- [ ] Pure black on pure white and highly saturated colors over large areas
      are not used without reason.
- [ ] Dark theme is not an inversion: surfaces of different depth, muted
      saturated colors.

## 5. Components and states
- [ ] Every screen/component has: empty, loading, error, partial and stale
      data, success, unavailable (with the reason).
- [ ] Interactive elements have hover, active, focus-visible, disabled.
- [ ] Buttons: one primary per area; labels are verbs; dangerous ones look
      different and do not sit next to frequent safe ones.
- [ ] Dangerous action: undo, or a confirmation that names the action;
      actions with different consequences are kept apart ("close window" ≠
      "stop").
- [ ] Icons from one set; an icon button has a text label, tooltip or
      `aria-label`.
- [ ] Response to an action <= ~100 ms; anything longer has an indicator/
      progress.
- [ ] Modals only when they cannot be avoided.

## 6. Forms
- [ ] Every field has a visible label, not only a placeholder.
- [ ] Correct input types (`type`, `inputmode`, `autocomplete`) and keyboard on
      mobile.
- [ ] Required status and format are explained before input, not after an
      error.
- [ ] The error is next to the field, as text (not only a red border), with a
      fix; entered data is not lost.
- [ ] Validation on leaving a field, not on every keystroke; the summary on
      submit.
- [ ] The submit button prevents double submission; status is visible while
      submitting.

## 7. Navigation and keyboard
- [ ] It is always clear where I am and how to go back; the current section is
      marked.
- [ ] Everything is reachable by keyboard; Tab order = visual order; no focus
      traps (except modals that can be exited with Esc).
- [ ] Focus is always visible (`outline: none` is not removed without a
      replacement).
- [ ] Shortcuts are shown in the interface; standard keys behave as expected
      (Esc closes, Enter confirms, `/` searches).

## 8. Accessibility
- [ ] Semantic elements: `header/nav/main`, `button` for actions, `a` for
      navigation, `table` with `th scope` for tables, proper `label`s.
- [ ] Headings and landmarks let a screen reader move through the page; there
      is a "skip to content" link.
- [ ] `alt` on meaningful images; empty `alt` on decorative ones.
- [ ] Dynamic error/status messages are announced (`role="status"`/
      `aria-live`), without spam.
- [ ] Touch targets >= 44×44 px (the WCAG 2.2 minimum is 24 px), with gaps
      between neighbors.
- [ ] `prefers-reduced-motion` is handled and font scaling up to 200% loses no
      content.
- [ ] ARIA only where native semantics fall short; wrong ARIA is worse than
      none.

## 9. Responsiveness
- [ ] Checked at 375, 768, 1280 px (and wide, >= 1600) or at 80×24 and a wide
      terminal.
- [ ] No horizontal page scroll (tables scroll inside their container or
      reflow).
- [ ] Long words, long numbers and names do not break the layout; wrapping or
      truncation with the full value on hover is used.
- [ ] Nothing "jumps" while loading (space is reserved).
- [ ] Dark theme is supported if the platform has one.

## 10. Copy and locale
- [ ] No `lorem ipsum`/placeholders; the real language of the domain.
- [ ] One term, one meaning; capitalization and punctuation are consistent.
- [ ] Errors do not blame the user and offer a fix; empty states explain what
      to do.
- [ ] Numbers/dates/currencies follow the locale; a non-breaking space between
      number and unit; the "−" minus; plural forms correct for the language (no
      "item(s)" hacks).
- [ ] Strings are not locked to a fixed width; they tolerate +30% length.

## 11. Speed
- [ ] No blocking font/script loads on the first screen; images have
      dimensions and `loading="lazy"` below the fold.
- [ ] Data updates happen in place: no flicker or loss of scroll position/
      selection; in a terminal, no full-screen redraw.
- [ ] Heavy operations do not block input.

## 12. Template mistakes (see also SKILL.md)
- [ ] No identical card "bricks" for everything.
- [ ] No gradients or decoration without function; no emoji instead of icons.
- [ ] No "OK/Cancel" instead of meaningful verbs; no "Are you sure?" without
      naming the action.
- [ ] No red/green as the only signal.
