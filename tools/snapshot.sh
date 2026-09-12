#!/bin/sh
# Screenshot an SVG as it looks N milliseconds into playback, using headless
# Chrome's virtual time so the CSS animation advances deterministically.
# Usage: tools/snapshot.sh file.svg milliseconds out.png
#
# Chrome is navigated directly to the SVG file (not wrapped in an <img> tag):
# an SVG embedded via <img src="..."> is rendered as a static image and its
# CSS animations do not advance with --virtual-time-budget, so the wrapper
# would always capture the initial frame. --run-all-compositor-stages-before-draw
# avoids an intermittent race where the screenshot is taken before the paint
# for the final virtual-time tick has been flushed.
set -e
svg=$(realpath "$1"); ms=$2; out=$3
size=$(sed -n 's/<svg[^>]*width="\([0-9]*\)" height="\([0-9]*\)".*/\1,\2/p' "$svg" | head -1)
google-chrome --headless=new --disable-gpu --hide-scrollbars --run-all-compositor-stages-before-draw \
  --window-size="$size" --virtual-time-budget="$ms" \
  --screenshot="$out" "file://$svg" 2>/dev/null
echo "wrote $out"
