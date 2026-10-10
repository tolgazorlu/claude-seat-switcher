# ccs

Choose which Claude account each terminal uses with
[Claude Code](https://docs.anthropic.com/en/docs/claude-code) and
[Hermes Agent](https://hermes-agent.nousresearch.com). For example, run a personal
Max plan in one terminal and a company Team seat in another. Each terminal uses
that account's own limits.

```
$ hermes
Claude hesabı:
  1) max      me@gmail.com        (Enter)
  2) work     me@company.com
  3) work2    me2@company.com
Seçim: 2
```

## Requirements

- macOS (it uses the Keychain-backed Claude Code login and BSD `sed`)
- bash and python3 (both ship with macOS)
- Claude Code (`claude`) and/or Hermes Agent (`hermes`), already installed
- `gh` (GitHub CLI), logged in, to clone this private repo

## Install

```sh
gh repo clone tolgazorlu/ccs ~/projects/ccs
~/projects/ccs/install.sh
```

The installer does two things:
- links `ccs` into `~/.local/bin`
- adds `eval "$(ccs shell-init)"` to `~/.zshrc`, which defines the `hermes`, `claude` and `ccs` shell functions

Open a new terminal once it finishes.

Update: `git -C ~/projects/ccs pull`. You don't need to run anything else, because the link points into the repo.

## Setup

```sh
ccs init max me@gmail.com        # the account you're already logged in with (~/.claude, default Hermes)
ccs add work me@company.com      # every other Claude account
ccs add work2 me2@company.com
ccs login work                   # browser login for Claude Code, then Hermes; email is checked
ccs status                       # asks Anthropic which account each side really uses
```

Log in with the right account in the browser. If claude.ai is already open with a
different account, use a private window. When the email doesn't match, `ccs login`
removes that login again.

Accounts are stored in `~/.config/ccs/accounts.tsv`. After a fresh OS install, run
the steps above again. Logins can't be carried over.

## Daily use

| Command | What it does |
|---|---|
| `hermes`, `claude` | ask which account, then remember the choice for this terminal (Enter keeps it) |
| `ccs use <name>` | switch this terminal without the menu |
| `ccs status` / `ccs whoami` | all accounts / this terminal |
| `ccs list` | registered accounts |
| `ccs remove <name> [--purge]` | unregister (`--purge` also deletes its login and data) |
| `export CCS_ASK=0` | turn the menu off |

Subcommands such as `hermes config` or `claude mcp` don't show the menu. They run on the terminal's current account.

## How it works

| | default account | other accounts |
|---|---|---|
| Claude Code | `~/.claude`, `CLAUDE_CONFIG_DIR` unset | `CLAUDE_CONFIG_DIR=~/.claude-<name>` |
| Hermes | default profile, borrows the `~/.claude` login | profile `~/.hermes/profiles/<name>` with its own Claude login and `auth.adopt_external_logins: false` |

Shared through symlinks:
- Claude Code: `CLAUDE.md`, settings, commands, agents, skills, hooks, plugins
- Hermes: skills and memories (use `ccs add <name> <email> --isolated` to keep them separate)

Separate per account: logins and session history. Hermes `.env` is copied once, when you run `ccs add`.

Safety: a Hermes profile with no Claude login of its own falls back to the default
profile's login, which spends the default account's limits. ccs won't start Hermes
on an account until that account has its own login.

## Notes

- Don't set `CLAUDE_CONFIG_DIR=~/.claude` yourself. Claude Code picks its Keychain
  item based on that variable, so the default account would look logged out.
- A running Hermes session can't switch accounts. Open another terminal instead.
