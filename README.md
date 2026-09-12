# svg_recorder

Record a terminal session as a small animated SVG.

    svg_recorder            # opens a shell; exit the shell to stop recording
    svg_recorder "cmd"      # records one command and stops when it exits
    svg_recorder render recording.cast -o out.svg

The SVG animates inside an `<img>` tag on GitHub and PyPI. On PyPI the README
must reference the absolute raw GitHub URL of the SVG, since PyPI cannot
resolve relative paths.
