# claude-seat-switcher

`seat` sets which Claude account ("seat") [Claude Code](https://code.claude.com) and
[Hermes Agent](https://hermes-agent.nousresearch.com) use, separately for each
terminal and each project. For example:

- a personal Max plan in one terminal
- a company Team seat in another
- a second Team seat in a third

Status: active, used daily across multiple terminals and projects.

```
$ hermes
Claude hesabı (hermes):
 ❯ 1) max    me@gmail.com      personal  5s ██░░░░░░  24%  7g ███░░░░░  36%
   2) work   me@company.com    company   5s █░░░░░░░  10%  7g ░░░░░░░░   3%
   3) work2  me2@company.com   company   giriş yok → seat login work2
   ↑↓ seç · Enter onayla · q vazgeç
seat ▸ max · me@gmail.com · 5s %24 · 7g %36
```

## What it does

- **Menu on launch.** `hermes` and `claude` open a menu with arrow-key selection and
  live 5-hour and 7-day limit bars. Whatever you pick stays in effect for that terminal.
- **Project rules.** Run `seat bind work,work2` inside a project. From then on, that
  folder uses `work` without asking, and `cd` into it switches the terminal over.
  The prompt shows the active seat, e.g. `⌁ work`.
- **Limit indicator.** The Claude Code status line shows `work · Opus · 5s 23% · 7g 41%`.
  `seat usage` lists every seat.
- **Limit handoff.** When Claude Code or Hermes stops because the seat hit its limit,
  `seat` asks: `work limiti doldu → work2 hesabına geçip devam edilsin mi? [E/h]`.
  - Claude Code continues the same session with `--resume`.
  - Hermes starts a new session seeded with the previous transcript.
  - Only seats allowed for the project are offered. Without a rule, only seats in the
    same group are offered, so personal work never moves onto a company seat.
  - It never switches without asking.
- **Hermes safety.** Each non-default seat has its own Hermes profile and its own
  login, and `auth.adopt_external_logins` is off. Hermes won't start on a seat that
  has no login. Otherwise it would silently spend the default seat's limits.
- **Company seats are isolated by default.** They get their own Hermes memories and
  none of your personal API keys.

## Requirements

- macOS, `python3` (included with macOS), zsh
- Claude Code and/or Hermes Agent
- `gh`, logged in (this repo is private)

## Install

```sh
gh repo clone tolgazorlu/claude-seat-switcher ~/projects/claude-seat-switcher
~/projects/claude-seat-switcher/install.sh
```

The installer:
- links `seat` into `~/.local/bin`
- adds `eval "$(seat shell-init)"` to `~/.zshrc`
- installs the Claude Code status line (backing up `settings.json` first)

Open a new terminal afterwards. To update: `git -C ~/projects/claude-seat-switcher pull`.

## Setup

```sh
seat init max me@gmail.com         # the login you already have (~/.claude + default Hermes)
seat add work me@company.com       # each additional seat; group = email domain
seat add work2 me2@company.com
seat login work                    # browser login for Claude Code, then Hermes; email is checked
seat doctor                        # what is missing
```

Make sure the browser is logged in to the right account. If claude.ai is already
open with a different one, use a private window. If the email doesn't match,
`seat login` signs out of that login again.

Config lives in `~/.config/seat/config.json`. After a fresh OS install, repeat the
steps above; logins can't be carried over.

## Commands

| Command | What it does |
|---|---|
| `hermes`, `claude` | menu, or the project rule if one exists; offers a handoff when the limit is hit |
| `seat use <name>` | switch this terminal without the menu |
| `seat bind a,b [dir]` / `seat unbind` / `seat projects` | project rules; the first seat is the default, the rest are fallbacks |
| `seat status` / `seat whoami` | login and real account for every seat / for this terminal |
| `seat usage [--refresh]` | limit bars |
| `seat list` · `seat doctor` · `seat remove <name> [--purge]` | |
| `SEAT_ASK=0` · `SEAT_PROMPT=0` | turn off the launch menu / the prompt tag |

Subcommands such as `hermes config` or `claude mcp` don't show the menu. They run on
the terminal's current seat.

## How it works

| | default seat | other seats |
|---|---|---|
| Claude Code | `~/.claude`, `CLAUDE_CONFIG_DIR` **unset** | `CLAUDE_CONFIG_DIR=~/.claude-<name>` (CLAUDE.md, settings, commands, agents, skills, hooks and plugins are symlinked from `~/.claude`) |
| Hermes | default profile, borrows the `~/.claude` login | `HERMES_HOME=~/.hermes/profiles/<name>`: own OAuth login; skills shared; memories shared only within the same group |

Limit data:
- **Claude Code:** the status line writes what Claude Code reports (`rate_limits`) to
  `~/.cache/seat/usage/`.
- **Hermes and the menu:** `api.anthropic.com/api/oauth/usage` is queried with the
  seat's still-valid token.

Tokens are never printed and never refreshed. Refresh tokens are single-use, so
refreshing one would sign Claude Code out.

## Rules and risks

- Anthropic says OAuth (subscription) login is meant for Claude Code and Anthropic's
  own apps ([legal-and-compliance](https://code.claude.com/docs/en/legal-and-compliance)).
  Hermes uses that login, so it falls outside that intent. On company seats, use
  Hermes with an API key or check with the company first.
- Rotating between seats to systematically get around limits goes against the usage
  policy. That's why `seat` always asks and only offers seats that are allowed for
  the project.
- Before making this repo public, the name needs to change: the Claude name can't be
  used in a product name.

## Credits

The following inspired the ideas; no code was copied:
- [uwuclxdy/clauth](https://github.com/uwuclxdy/clauth) (MIT): usage bars, fallback chain
- [Nemo-Illusionist/claude-code-account-switcher](https://github.com/Nemo-Illusionist/claude-code-account-switcher) (MIT): directory binding
- [inulute/cux](https://github.com/inulute/cux) (GPL-3.0): per-project seat pools, resuming after a switch

## Development

```sh
python3 -m unittest discover -s tests     # offline, throwaway HOME, never touches real logins
```
