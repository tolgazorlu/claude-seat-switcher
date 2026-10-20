# hermes-seats

Pick which Claude account ("seat") [Claude Code](https://code.claude.com) and
[Hermes Agent](https://hermes-agent.nousresearch.com) use, per terminal and per project.

```
$ hermes
 ❯ 1) max    me@gmail.com      personal  5s ██░░░░░░  24%  7g ███░░░░░  36%
   2) work   me@company.com    company   5s █░░░░░░░  10%  7g ░░░░░░░░   3%
   3) work2  me2@company.com   company   giriş yok → seat login work2
```

## Install

Paste this into Claude Code, Hermes or any coding agent on your Mac:

```text
Install hermes-seats on this Mac. Clone https://github.com/tolgazorlu/hermes-seats
into ~/projects/hermes-seats (git pull if it already exists) and run its install.sh.
Then ask me which Claude accounts I use (a short name and the email for each), run
`seat init <name> <email>` for the login I already have and `seat add <name> <email>` for the
others, and finish with `seat doctor`. Do not run `seat login` yourself: it opens a browser, so
give me the exact `seat login <name>` commands to run in a new terminal.
```

Or by hand (macOS, zsh, `python3`, `git`):

```sh
git clone https://github.com/tolgazorlu/hermes-seats ~/projects/hermes-seats
~/projects/hermes-seats/install.sh   # links seat, edits ~/.zshrc, adds the status line
seat init max me@gmail.com           # the login you already have
seat add work me@company.com         # every other seat; group = email domain
seat login work                      # browser login, the email is verified
```

Update with `git -C ~/projects/hermes-seats pull`.

## Features

- **Priority order:** `seat order a,b,c` sets the chain. `claude` and `hermes` start on the
  first seat with limit left (under 95% of the 5h and 7d windows); `seat use <name>` pins one.
- **Project rules:** `seat bind work,work2` makes a folder use `work`; `cd` switches the terminal.
- **Status line:** `work · Opus · 5s 23% · 7g 41%` inside Claude Code.
- **Limit handoff:** when the session ends on a seat at 95% or more (or on a limit error),
  `seat` moves to the next allowed seat in order without asking and resumes the same session.
  It never moves personal work onto a company seat. `SEAT_AUTO=0` brings back the launch menu
  and the confirm prompt.
- **Isolation:** each extra seat has its own Claude config dir, Hermes profile and login.
  Company seats get their own Hermes memories and no personal Hermes API keys; Claude Code
  settings, hooks and skills stay shared.

## Commands

| Command | |
|---|---|
| `seat use <name>` | switch this terminal |
| `seat bind a,b [dir]` · `unbind` · `projects` | project rules (first = default) |
| `seat status` · `whoami` · `usage` | logins, current account, limit bars |
| `seat order a,b,c` · `rename <old> <new>` | priority chain, rename (logins kept) |
| `seat list` · `doctor` · `remove <name> [--purge]` | manage seats |
| `SEAT_AUTO=0` · `SEAT_ASK=0` · `SEAT_PROMPT=0` | menu + confirm / no seat choice / no prompt tag |

## How it works

Extra seats run with `CLAUDE_CONFIG_DIR=~/.claude-<name>` (settings, skills, hooks symlinked
from `~/.claude`) and `HERMES_HOME=~/.hermes/profiles/<name>`. Usage comes from Claude Code's
status line and `api.anthropic.com/api/oauth/usage`. Tokens are never printed or refreshed.
Config: `~/.config/seat/config.json`.

## Caveats

- OAuth subscription logins are meant for Claude Code and Anthropic's own apps
  ([terms](https://code.claude.com/docs/en/legal-and-compliance)). On company seats, give
  Hermes an API key or ask the company first.

## About automatic switching

Switching is automatic by default, but only when a session ends, never mid-request, and only
between seats allowed for the project (or the same group). Keep in mind:

- Rotating accounts to get around usage limits is a gray area under Anthropic's terms at
  best, and the account risk lands on you (and on your company for Team seats).
- The launch line (`seat ▸ name · email · 5s %..`) always shows which account is spending.

Inspired by [clauth](https://github.com/uwuclxdy/clauth), [claude-code-account-switcher](https://github.com/Nemo-Illusionist/claude-code-account-switcher)
and [cux](https://github.com/inulute/cux); no code copied. Tests: `python3 -m unittest discover -s tests`.
