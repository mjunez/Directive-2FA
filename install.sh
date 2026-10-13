#!/usr/bin/env bash
# Directive-2FA Installer
# Instala el framework 2FA en ~/.hermes/2fa/ y el skill en ~/.hermes/skills/directive-2fa/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_2FA="$HOME/.hermes/2fa"
TARGET_SKILL="$HOME/.hermes/skills/directive-2fa"

echo "=== Directive-2FA Installer ==="
echo "Source: $SCRIPT_DIR"
echo "Target 2FA: $TARGET_2FA"
echo "Target Skill: $TARGET_SKILL"
echo

# Crear directorios
mkdir -p "$TARGET_2FA"/{pending,tokens}
mkdir -p "$TARGET_SKILL"/references

chmod 700 "$TARGET_2FA/pending" "$TARGET_2FA/tokens"

# Copiar scripts
echo "Copiando scripts..."
cp "$SCRIPT_DIR/scripts/2fa-challenger" "$TARGET_2FA/"
cp "$SCRIPT_DIR/scripts/2fa-poller" "$TARGET_2FA/"
cp "$SCRIPT_DIR/scripts/2fa-validator" "$TARGET_2FA/"
cp "$SCRIPT_DIR/scripts/2fa-wait" "$TARGET_2FA/"
cp "$SCRIPT_DIR/scripts/2fa-stop-childs" "$TARGET_2FA/"
cp "$SCRIPT_DIR/scripts/terminal_2fa.py" "$TARGET_2FA/"
cp "$SCRIPT_DIR/scripts/webform_server.py" "$TARGET_2FA/"

chmod +x "$TARGET_2FA/2fa-challenger"
chmod +x "$TARGET_2FA/2fa-poller"
chmod +x "$TARGET_2FA/2fa-validator"
chmod +x "$TARGET_2FA/2fa-wait"
chmod +x "$TARGET_2FA/2fa-stop-childs"

# Copiar skill
echo "Copiando skill..."
cp -r "$SCRIPT_DIR/skill/"* "$TARGET_SKILL/"

# Verificar sintaxis
echo "Verificando sintaxis..."
for f in "$TARGET_2FA/2fa-challenger" "$TARGET_2FA/2fa-poller" "$TARGET_2FA/2fa-validator" "$TARGET_2FA/2fa-wait" "$TARGET_2FA/2fa-stop-childs" "$TARGET_2FA/terminal_2fa.py" "$TARGET_2FA/webform_server.py"; do
    python3 -m py_compile "$f" && echo "  ✅ $f" || { echo "  ❌ $f"; exit 1; }
done

# Verificar skill
if [[ -f "$TARGET_SKILL/SKILL.md" ]]; then
    echo "  ✅ SKILL.md presente"
else
    echo "  ❌ SKILL.md faltante"
    exit 1
fi

echo
echo "=== Instalación completada ==="
echo
echo "Próximos pasos:"
echo "  1. Configura ~/.hermes/.env con _2FA_WEB_PORT y 2FA_SECRET"
echo "  2. Recarga Hermes para cargar el skill directive-2fa"
echo "  3. Prueba: python3 ~/.hermes/2fa/2fa-challenger \"test-install\""