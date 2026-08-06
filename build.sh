#!/bin/sh
# Empaqueta el juego en UN solo archivo ejecutable: m5.pyz
#
# Usa zipapp, de la biblioteca estandar: no descarga ni compila nada. El .pyz
# resultante se puede copiar suelto a cualquier Linux o macOS con Python 3 y
# ejecutarse directamente (./m5.pyz).

set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$DIR"

rm -rf build m5.pyz
mkdir -p build/m5
# solo el paquete: ni pruebas, ni cache de bytecode
for f in m5/*.py; do
    cp "$f" build/m5/
done

# zipapp arranca por el __main__.py de la raiz del archivo; el paquete ya trae
# el suyo, asi que la raiz solo lo invoca
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
echo "listo: $DIR/m5.pyz  ($(wc -c < m5.pyz | tr -d ' ') bytes)"
echo "probalo con: ./m5.pyz --version"
