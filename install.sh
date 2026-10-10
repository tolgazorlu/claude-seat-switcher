#!/usr/bin/env bash
# Install seat: link it onto PATH, load its shell functions in zsh, and add the
# Claude Code status line. Safe to run again; it only adds what is missing.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${SEAT_BIN_DIR:-$HOME/.local/bin}"
RC="$HOME/.zshrc"
INIT_LINE='command -v seat >/dev/null && eval "$(seat shell-init)"'

command -v python3 >/dev/null 2>&1 || { echo "python3 is required"; exit 1; }

mkdir -p "$BIN_DIR"
chmod +x "$REPO_DIR/seat"
ln -sf "$REPO_DIR/seat" "$BIN_DIR/seat"
echo "✓ $BIN_DIR/seat -> $REPO_DIR/seat"

# Upgrade from the old `ccs` name: drop its link and rc line.
if [[ -L "$BIN_DIR/ccs" ]]; then rm "$BIN_DIR/ccs"; echo "✓ removed old ccs link"; fi
touch "$RC"
if grep -qF 'ccs shell-init' "$RC"; then
  cp "$RC" "$RC.seat-bak"
  grep -vF 'ccs shell-init' "$RC" | grep -vF '# ccs:' > "$RC.seat-tmp" && mv "$RC.seat-tmp" "$RC"
  echo "✓ removed old ccs line from $RC (backup: $RC.seat-bak)"
fi
if ! grep -qF 'seat shell-init' "$RC"; then
  printf '\n# seat: Claude seat per terminal/project (menu, limits, project rules)\n%s\n' "$INIT_LINE" >> "$RC"
  echo "✓ added shell functions to $RC"
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "! $BIN_DIR is not on PATH; add to $RC: export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

"$BIN_DIR/seat" setup || true

for dep in claude hermes; do
  command -v "$dep" >/dev/null 2>&1 || echo "! $dep not found (optional, but seat manages it)"
done

cat <<'EOF'

Next (open a new terminal first):
  seat init max you@gmail.com        # name the login you already have
  seat add work you@company.com      # every other Claude seat
  seat login work                    # browser login, email is verified
  seat status
EOF
