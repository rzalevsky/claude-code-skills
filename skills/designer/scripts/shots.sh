#!/usr/bin/env bash
# Screenshots of a page in 4 variants: mobile 375, tablet 768, desktop 1280, and
# desktop 1280 in dark theme. No dependencies beyond an installed Chrome/Chromium.
#
# Usage: shots.sh <url | path-to-html-or-svg> [output-dir] [window-height]
#   output-dir     default ./shots (use the session scratchpad or a temp dir for
#                  throwaway files, not the repository)
#   window-height  default 900; raise it for long pages (e.g. 2400)
#
# Then open the PNGs with the Read tool. The script does NOT detect horizontal
# scrolling; check it in a browser: document.documentElement.scrollWidth <= window.innerWidth.
set -euo pipefail

target="${1:?Usage: shots.sh <url|file.html> [output-dir] [window-height]}"
outdir="${2:-./shots}"
height="${3:-900}"

chrome=""
for c in google-chrome-stable google-chrome chromium chromium-browser chrome; do
  if command -v "$c" >/dev/null 2>&1; then chrome="$c"; break; fi
done
if [ -z "$chrome" ]; then
  echo "Chrome/Chromium not found: screenshots unavailable. Say so in your report; do not claim a visual check." >&2
  exit 2
fi

case "$target" in
  http://*|https://*|file://*) url="$target" ;;
  *)
    [ -f "$target" ] || { echo "File not found: $target" >&2; exit 1; }
    url="file://$(realpath "$target")"
    ;;
esac

mkdir -p "$outdir"
extra=()
[ "$(id -u)" -eq 0 ] && extra+=(--no-sandbox)

# shot <name> <width> <blink preferredColorScheme>
# NOTE: in Chrome the enum is inverted: 0 = DARK, 1 = LIGHT (observed in screenshots,
# Chrome 153). Always confirm by eye that *-dark.png is actually dark.
shot() {
  "$chrome" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --virtual-time-budget=3000 --blink-settings="preferredColorScheme=$3" \
    --window-size="$2,$height" --screenshot="$outdir/$1.png" \
    ${extra[@]+"${extra[@]}"} "$url" >/dev/null 2>&1 || { echo "Screenshot failed: $1" >&2; return 1; }
  echo "$outdir/$1.png"
}

shot mobile-375         375  1
shot tablet-768         768  1
shot desktop-1280      1280  1
shot desktop-1280-dark 1280  0
