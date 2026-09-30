# Mobile and desktop apps

General rule: **follow platform conventions.** People already know how their
system works; unusual custom navigation costs them effort. Use native
components and system fonts, themes and gestures, and apply custom styling
only selectively.

## Contents
1. Mobile · 2. Desktop · 3. Cross-platform frameworks · 4. Verification

## 1. Mobile (iOS / Android)

**References:** Apple Human Interface Guidelines for iOS, Material Design 3
for Android.

- **Touch.** Targets >= 44×44 pt (iOS) / 48×48 dp (Android), gap between
  neighbors >= 8 dp. Primary actions in the thumb zone (lower half of the
  screen).
- **Navigation.** Up to 5 equal-weight sections: a bottom tab bar; do not hide
  primary navigation in a "hamburger". Going back is the system gesture/back
  button and always predictable. Keep hierarchy depth small.
- **Safe areas.** Account for notches, rounded corners, gesture bars and the
  keyboard; content is not under the notch, inputs are not covered by the
  keyboard.
- **Gestures.** Swipes and long press only as accelerators: every gesture
  action has a visible alternative.
- **Input.** The right keyboard type (email, number, phone), autofill,
  minimal typing: choose from a list instead of typing, sensible defaults,
  biometrics instead of a password where appropriate.
- **Permissions.** Ask at the moment they are needed and explain why; a denial
  must not break the app.
- **Network and offline.** Weak or lost connectivity is a normal state: show
  cache with a note, queue actions, retry; skeletons instead of empty screens.
- **Text and sizes.** Support the system font size (Dynamic Type / font scale)
  up to the extremes without clipping; dark theme; orientation if it makes
  sense for the scenario.
- **Feedback.** Instant response to touch; light haptics rarely and with
  purpose; dialogs only when a decision is needed.
- **Resilience.** Resume after backgrounding and process death; do not lose
  what was typed.

## 2. Desktop (Electron / Tauri / Qt / GTK / native)

- **Menus and shortcuts.** The platform's standard menu; familiar shortcuts:
  Ctrl/Cmd+S, Z, Shift+Z/Y, C/V/X, F (find), W (close), Q (quit), "," (settings
  on macOS); show them in the menu.
- **Windows.** Remember size and position; a minimum size at which nothing
  breaks; multi-window/multi-monitor support where appropriate; correct
  behavior on resize and scaling (HiDPI).
- **Keyboard first.** Full navigation without a mouse; visible focus; quick
  actions; a command palette for complex apps.
- **Direct manipulation.** Drag and drop, context menus (right click) for
  actions on an object; undo/redo wherever possible.
- **System theme.** Follow the OS light/dark theme, accent color and system
  font; do not look like "a web page in a frame" where the platform expects
  otherwise.
- **Background work.** Tray/dock and notifications with respect: no spam, with
  a way to turn them off; long tasks with progress and cancellation.
- **Electron specifics.** Do not block the main process; keep windows light;
  use native file dialogs and notifications; make updates clear and
  unobtrusive.
- **Accessibility.** Support screen readers and system settings (contrast,
  text size, reduced motion).

## 3. Cross-platform frameworks (Flutter, React Native, Compose, MAUI)
- Use platform-adaptive components (switches, navigation, pickers) rather than
  a single "drawn" version for everyone, if the audience is ordinary platform
  users.
- Shared design-system tokens (colors, fonts, spacing) in one place; platform
  differences live in the components.
- Check at real sizes and in dark theme; on Android, different densities and
  font sizes.

## 4. Verification
- Run on an emulator/simulator/real window and **look at screenshots** (for
  native windows, capture with the platform's tools and open with `Read`).
- Check: small and large screens, dark theme, enlarged font, empty data, a
  network error, rotation, the input keyboard, the main scenario in the fewest
  steps.
- If the platform cannot be run in this environment, say plainly in the report
  that only code/mockups were reviewed.
