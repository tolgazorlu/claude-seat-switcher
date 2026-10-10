#!/usr/bin/env bash
# Install ccs: link it onto PATH and load its shell functions in zsh/bash.
# Safe to run again; it only adds what is missing.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${CCS_BIN_DIR:-$HOME/.local/bin}"
INIT_LINE='command -v ccs >/dev/null && eval "$(ccs shell-init)"'

mkdir -p "$BIN_DIR"
chmod +x "$REPO_DIR/ccs"
ln -sf "$REPO_DIR/ccs" "$BIN_DIR/ccs"
echo "✓ $BIN_DIR/ccs -> $REPO_DIR/ccs"

for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
  [[ -f "$rc" || "$rc" == "$HOME/.zshrc" ]] || continue
  touch "$rc"
  if ! grep -qF 'ccs shell-init' "$rc"; then
    printf '\n# ccs: ask which Claude account hermes/claude should use\n%s\n' "$INIT_LINE" >> "$rc"
    echo "✓ added shell functions to $rc"
  fi
done

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "! $BIN_DIR is not on PATH; add to your shell rc: export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

for dep in python3 claude hermes; do
  command -v "$dep" >/dev/null 2>&1 || echo "! $dep not found; install it before using ccs"
done

cat <<'EOF'

Next (open a new terminal first):
  ccs init max you@personal.com      # name your existing Claude Code / Hermes login
  ccs add work you@company.com       # each extra Claude account
  ccs login work                     # browser login, email is verified
  ccs status
EOF
