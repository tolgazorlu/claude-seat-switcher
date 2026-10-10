# ccs

Choose which Claude account Claude Code and Hermes use, per terminal. Example:
personal Max (`tolgazorlu17@gmail.com`) in one terminal, a company Team seat
(`tolga@viby.dev`) in another, and another Team seat in a third. Each terminal
uses its own account's limits.

## Setup (once)

```sh
ccs init max tolgazorlu17@gmail.com   # name the existing setup (~/.claude + default Hermes)
ccs add viby tolga@viby.dev           # register another Claude account
ccs login viby                        # browser login for Claude Code, then for Hermes
ccs status                            # asks Anthropic which account each side is really using
```

`ccs login` checks that you logged in with the registered email. On a mismatch
it logs out of / deletes that login.

## Daily use

Running `hermes` or `claude` asks:

```
Claude hesabı:
  1) max      tolgazorlu17@gmail.com   (Enter)
  2) viby     tolga@viby.dev
Seçim:
```

The choice sticks to that terminal. Enter keeps the current one.

- `ccs use <name>`: switch the terminal without the menu.
- `export CCS_ASK=0`: turn the menu off.
- Subcommands such as `hermes config` or `claude mcp` don't ask. They run on the
  terminal's current account.

Needs `eval "$(ccs shell-init)"` in `~/.zshrc`. That line defines the `hermes`,
`claude` and `ccs` shell functions.

## How it works

| | default account (`max`) | other accounts `<name>` |
|---|---|---|
| Claude Code | `~/.claude`, `CLAUDE_CONFIG_DIR` unset | `CLAUDE_CONFIG_DIR=~/.claude-<name>` |
| Hermes | default profile, borrows the `~/.claude` login | `HERMES_HOME=~/.hermes/profiles/<name>`, with its own Claude OAuth login and `auth.adopt_external_logins: false` |

Shared through symlinks:
- Claude Code: `CLAUDE.md`, settings, commands, agents, skills, hooks, plugins
- Hermes: skills and memories

Separate per account: logins, session history, Hermes MCP OAuth tokens.
`.env` is copied once, at `ccs add` time.

Safety: if a Hermes profile has no Claude credential of its own, Hermes falls back
to the default profile's login and bills the Max account. ccs therefore won't start
Hermes on an account until that account has its own login.

## Notes

- Don't set `CLAUDE_CONFIG_DIR=~/.claude` yourself. Claude Code picks its Keychain
  item based on that variable, so the default account would look logged out.
- A running Hermes session can't change accounts. Open another terminal instead.
- Written in bash 3.2 with the system python3, so there's nothing to build.
  Install: `ln -s "$PWD/ccs" ~/.local/bin/ccs`.
