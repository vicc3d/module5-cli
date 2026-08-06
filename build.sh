#!/bin/sh
# Packages the game into ONE executable file: m5.pyz
#
# Uses zipapp, from the standard library: nothing downloaded or compiled. The
# resulting .pyz can be copied on its own to any Linux or macOS with Python 3
# and run directly (./m5.pyz).

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$DIR"

rm -rf build m5.pyz
mkdir -p build/m5
# just the package: no tests, no bytecode cache
for f in m5/*.py; do
    cp "$f" build/m5/
done

# zipapp starts from the __main__.py at the archive root; the package already
# has its own, so the root one just calls it
cat > build/__main__.py <<'PYEOF'
import sys

from m5.__main__ import main

sys.exit(main())
PYEOF

python3 - <<'EOF'
import zipapp
zipapp.create_archive("build", target="m5.pyz",
                      interpreter="/usr/bin/env python3", compressed=True)
EOF

chmod +x m5.pyz
rm -rf build
echo "done: $DIR/m5.pyz  ($(wc -c < m5.pyz | tr -d ' ') bytes)"
echo "try it: ./m5.pyz --version"
