# ccs

Run Claude Code and Hermes under several Claude accounts side by side on one Mac
(e.g. a personal Max plan in one terminal, a Team plan in another).

## How it works

| Piece | Default account | Extra account `<name>` |
|---|---|---|
| Claude Code | `~/.claude` (`CLAUDE_CONFIG_DIR` unset) | `~/.claude-<name>` via `CLAUDE_CONFIG_DIR` |
| Hermes | default profile, borrows the `~/.claude` login | profile `<name>` with its **own** Anthropic OAuth login, `auth.adopt_external_logins: false` |
| Commands | `claude`, `hermes` | `claude-<name>`, `hermes-<name>` |

Shared across accounts by symlink: Claude Code `CLAUDE.md`, `settings.json`,
`commands`, `agents`, `skills`, `hooks`, `plugins`; Hermes `skills` and
`memories` (use `ccs add <name> --isolated` to keep them separate).
Not shared: logins, sessions/history, Hermes MCP OAuth tokens, `.env` (copied once).

Safety: `hermes-<name>` / `ccs use <name>` refuse to start Hermes unless the profile
has its own Anthropic credential. A profile with zero Anthropic credentials reads
the root profile's pool, which would silently bill the default account.

## Usage

```sh
ccs init max            # name the existing setup
ccs add team            # create ~/.claude-team, Hermes profile "team", wrappers
ccs login team          # browser login for Claude Code, then for Hermes (pick the Team org both times)
ccs status              # asks Anthropic which account each side really uses

claude-team             # Claude Code on Team
hermes-team             # Hermes on Team
ccs use team            # switch this terminal: plain `claude` and `hermes` now use Team
ccs use max             # back
ccs run team claude -c  # one-off
```

`ccs use` needs the shell function: `eval "$(ccs shell-init)"` in `~/.zshrc`.

## Notes

- Never set `CLAUDE_CONFIG_DIR=~/.claude` explicitly: Claude Code keys its Keychain
  item on the variable, so the default account would look logged out.
- Hermes cannot switch accounts inside a running session; start `hermes-<name>`
  (or `ccs use <name>` then `hermes`) in another terminal.
- Plain bash 3.2 + system python3; no build step. Install: `ln -s "$PWD/ccs" ~/.local/bin/ccs`.
