"""Unit tests for seat. Run: python3 -m unittest discover -s tests

Every test runs against a throwaway HOME with SEAT_OFFLINE=1, so nothing touches the
real ~/.claude, ~/.hermes, the Keychain or the network.
"""
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_seat(home):
    os.environ.update({"HOME": str(home), "SEAT_OFFLINE": "1", "NO_COLOR": "1"})
    for k in ("SEAT_ACCOUNT", "CCS_ACCOUNT", "CLAUDE_CONFIG_DIR", "HERMES_HOME",
              "SEAT_CONFIG_DIR", "SEAT_CACHE_DIR", "SEAT_HERMES_ROOT"):
        os.environ.pop(k, None)
    loader = importlib.machinery.SourceFileLoader("seat_under_test", str(ROOT / "seat"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def run(mod, fn, *args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(mod.Config(), list(args))
    return buf.getvalue()


class SeatTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home)
        self.old_env = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self.old_env)))
        legacy = self.home / ".config" / "ccs"
        legacy.mkdir(parents=True)
        (legacy / "accounts.tsv").write_text(
            f"max\t{self.home}/.claude\tdefault\tme@gmail.com\n"
            f"viby\t{self.home}/.claude-viby\tviby\tme@viby.dev\n"
            f"viby2\t{self.home}/.claude-viby2\tviby2\tme2@viby.dev\n")
        self.seat = load_seat(self.home)
        self.seat.tty_write = lambda text: None
        self.cwd = self.home / "projects" / "viby-app"
        self.cwd.mkdir(parents=True)
        self.old_cwd = os.getcwd()
        os.chdir(self.cwd)
        self.addCleanup(os.chdir, self.old_cwd)

    def login_claude(self, name):
        d = self.home / (".claude" if name == "max" else f".claude-{name}")
        f = (self.home / ".claude.json") if name == "max" else d / ".claude.json"
        d.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"oauthAccount": {"emailAddress": f"{name}@x"}}))

    def set_usage(self, name, five, ts=None):
        cfg = self.seat.Config()
        self.seat.cache_write(cfg.get(name), {"ts": ts or time.time(), "src": "statusline",
                                              "five_hour": {"pct": five, "resets": time.time() + 3600}})

    # ── config ──
    def test_legacy_migration_assigns_groups(self):
        cfg = self.seat.Config()
        self.assertEqual([a.name for a in cfg.accounts], ["max", "viby", "viby2"])
        self.assertEqual([a.group for a in cfg.accounts], ["personal", "viby", "viby"])
        self.assertTrue(cfg.default.is_default)
        self.assertEqual(oct(self.seat.CONFIG.stat().st_mode & 0o777), "0o600")

    def test_rule_longest_match_respects_path_boundary(self):
        run(self.seat, self.seat.cmd_bind, "viby,viby2", str(self.home / "projects" / "viby-app"))
        run(self.seat, self.seat.cmd_bind, "max", str(self.home / "projects"))
        cfg = self.seat.Config()
        self.assertEqual(cfg.rule_for(self.cwd / "src")["accounts"], ["viby", "viby2"])
        sibling = self.home / "projects" / "viby-app2"
        sibling.mkdir()
        self.assertEqual(cfg.rule_for(sibling)["accounts"], ["max"])
        self.assertIsNone(cfg.rule_for(self.home))

    def test_allowed_without_rule_stays_in_group(self):
        cfg = self.seat.Config()
        self.assertEqual([a.name for a in cfg.allowed(self.home, cfg.get("max"))], ["max"])
        self.assertEqual([a.name for a in cfg.allowed(self.home, cfg.get("viby"))], ["viby", "viby2"])

    def test_env_script(self):
        cfg = self.seat.Config()
        self.assertIn("unset CLAUDE_CONFIG_DIR HERMES_HOME", cfg.get("max").env_script())
        s = cfg.get("viby").env_script()
        self.assertIn(f"CLAUDE_CONFIG_DIR={self.home}/.claude-viby", s)
        self.assertIn(f"HERMES_HOME={self.home}/.hermes/profiles/viby", s)

    def test_slug_matches_claude_code(self):
        self.assertEqual(self.seat.slug("/Users/t/projects/kolay-barkod"), "-Users-t-projects-kolay-barkod")
        self.assertEqual(self.seat.slug("/a/b.c_d"), "-a-b-c-d")

    def test_add_company_seat_defaults_to_isolated(self):
        self.seat.shutil.which = lambda name: None   # skip the Hermes profile part
        out = run(self.seat, self.seat.cmd_add, "acme", "me@acme.io")
        acc = self.seat.Config().get("acme")
        self.assertTrue(acc.isolated)
        self.assertEqual(acc.group, "acme")
        self.assertIn("izole", out)
        with self.assertRaises(SystemExit):
            run(self.seat, self.seat.cmd_add, "acme", "other@acme.io")

    # ── usage / status line ──
    def test_statusline_records_usage_per_seat(self):
        os.environ["SEAT_ACCOUNT"] = "viby"
        payload = {"model": {"display_name": "Opus"},
                   "rate_limits": {"five_hour": {"used_percentage": 23.5, "resets_at": time.time() + 600},
                                   "seven_day": {"used_percentage": 41}}}
        sys.stdin = io.StringIO(json.dumps(payload))
        try:
            out = run(self.seat, self.seat.cmd_statusline)
        finally:
            sys.stdin = sys.__stdin__
        self.assertIn("viby", out)
        self.assertIn("5s 24%", out)
        cached = self.seat.cache_read(self.seat.Config().get("viby"))
        self.assertEqual(cached["five_hour"]["pct"], 23.5)

    def test_expired_window_is_not_limited(self):
        u = {"ts": time.time() - 7200, "five_hour": {"pct": 100, "resets": time.time() - 60}}
        self.assertFalse(self.seat.is_limited(u))
        u["five_hour"]["resets"] = time.time() + 60
        self.assertTrue(self.seat.is_limited(u))

    # ── limit handoff ──
    def write_transcript(self, acc_dir, lines):
        folder = acc_dir / "projects" / self.seat.slug(self.cwd.resolve())
        folder.mkdir(parents=True, exist_ok=True)
        f = folder / "abc-123.jsonl"
        f.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
        return f

    def test_transcript_limit_detection(self):
        err = {"type": "assistant", "isApiErrorMessage": True,
               "message": {"content": [{"type": "text", "text": "Claude AI usage limit reached|1760000000"}]}}
        f = self.write_transcript(self.home / ".claude", [{"type": "user", "message": {}}, err])
        self.assertTrue(self.seat.transcript_hit_limit(f))
        f = self.write_transcript(self.home / ".claude", [err, {"type": "user", "message": {}}])
        self.assertFalse(self.seat.transcript_hit_limit(f))
        old = dict(err, timestamp="2026-01-01T10:00:00.000Z")   # carried over from an earlier run
        f = self.write_transcript(self.home / ".claude", [old])
        self.assertFalse(self.seat.transcript_hit_limit(f, since=time.time()))
        self.assertTrue(self.seat.transcript_hit_limit(f))

    def test_after_offers_allowed_seat_and_carries_session(self):
        for n in ("viby", "viby2"):
            self.login_claude(n)
        run(self.seat, self.seat.cmd_bind, "viby,viby2")
        os.environ["SEAT_ACCOUNT"] = "viby"
        since = time.time() - 30
        self.write_transcript(self.home / ".claude-viby", [{"type": "assistant", "message": {}}])
        self.set_usage("viby", 100)
        self.set_usage("viby2", 12)
        self.seat.confirm = lambda q, default_yes=True: True
        out = run(self.seat, self.seat.cmd_after, "claude", str(since))
        self.assertIn(f"CLAUDE_CONFIG_DIR={self.home}/.claude-viby2", out)
        self.assertIn("set -- --resume abc-123", out)
        copied = self.home / ".claude-viby2" / "projects" / self.seat.slug(self.cwd.resolve()) / "abc-123.jsonl"
        self.assertTrue(copied.exists())

    def test_after_never_moves_personal_work_to_company_seat(self):
        for n in ("max", "viby"):
            self.login_claude(n)
        os.environ["SEAT_ACCOUNT"] = "max"
        self.write_transcript(self.home / ".claude", [{"type": "assistant", "message": {}}])
        self.set_usage("max", 100)
        self.set_usage("viby", 0)
        self.seat.confirm = lambda q, default_yes=True: self.fail("must not offer a company seat")
        self.assertEqual(run(self.seat, self.seat.cmd_after, "claude", str(time.time() - 30)), "")

    def test_after_silent_when_not_limited(self):
        self.login_claude("viby2")
        run(self.seat, self.seat.cmd_bind, "viby,viby2")
        os.environ["SEAT_ACCOUNT"] = "viby"
        self.write_transcript(self.home / ".claude-viby", [{"type": "assistant", "message": {}}])
        self.set_usage("viby", 40)
        self.assertEqual(run(self.seat, self.seat.cmd_after, "claude", str(time.time() - 30)), "")

    def test_guard_blocks_hermes_on_seat_without_own_login(self):
        os.environ["SEAT_ACCOUNT"] = "viby"
        with self.assertRaises(SystemExit):
            run(self.seat, self.seat.cmd_guard)
        prof = self.home / ".hermes" / "profiles" / "viby"
        prof.mkdir(parents=True)
        (prof / "config.yaml").write_text("auth:\n  adopt_external_logins: false\n")
        (prof / "auth.json").write_text(json.dumps({"credential_pool": {"anthropic": [
            {"source": "manual:hermes_pkce", "label": "seat-viby"}]}}))
        run(self.seat, self.seat.cmd_guard)   # own login → allowed

    def test_email_change_keeps_seat_and_group(self):
        run(self.seat, self.seat.cmd_email, "viby", "contact@viby.com")
        acc = self.seat.Config().get("viby")
        self.assertEqual((acc.email, acc.group), ("contact@viby.com", "viby"))

    def test_cd_hook_switches_into_bound_project(self):
        run(self.seat, self.seat.cmd_bind, "viby")
        os.environ["SEAT_ACCOUNT"] = "max"
        self.assertIn("SEAT_ACCOUNT=viby", run(self.seat, self.seat.cmd_cd))
        os.environ["SEAT_ACCOUNT"] = "viby"
        self.assertEqual(run(self.seat, self.seat.cmd_cd), "")


if __name__ == "__main__":
    unittest.main()
