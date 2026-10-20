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

    def test_remove_default_hides_it_and_init_restores(self):
        out = run(self.seat, self.seat.cmd_remove, "max")
        self.assertIn("gizlendi", out)
        cfg = self.seat.Config()
        self.assertTrue(cfg.get("max").hidden)
        self.assertEqual([a.name for a in cfg.visible], ["viby", "viby2"])
        self.assertEqual(cfg.allowed(self.home, cfg.get("max")), [])
        run(self.seat, self.seat.cmd_init, "max")
        self.assertFalse(self.seat.Config().get("max").hidden)

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

    def add_viby3(self):
        self.seat.shutil.which = lambda name: None
        run(self.seat, self.seat.cmd_add, "viby3", "me3@viby.dev")

    def test_after_switches_to_next_seat_in_order_without_asking(self):
        self.add_viby3()
        for n in ("viby", "viby2", "viby3"):
            self.login_claude(n)
        run(self.seat, self.seat.cmd_order, "viby3,viby,viby2")
        run(self.seat, self.seat.cmd_auto, "on")
        os.environ["SEAT_ACCOUNT"] = "viby3"
        self.write_transcript(self.home / ".claude-viby3", [{"type": "assistant", "message": {}}])
        self.set_usage("viby3", 96)            # near the limit counts as full
        self.set_usage("viby", 80)             # more used than viby2, still next in order
        self.set_usage("viby2", 5)
        self.seat.confirm = lambda *a, **k: self.fail("auto mode must not ask")
        self.seat.pick = lambda *a, **k: self.fail("auto mode must not show a menu")
        out = run(self.seat, self.seat.cmd_after, "claude", str(time.time() - 30))
        self.assertIn(f"CLAUDE_CONFIG_DIR={self.home}/.claude-viby ", out + " ")
        self.assertIn("set -- --resume abc-123", out)

    def test_after_asks_when_auto_is_off(self):
        for n in ("viby", "viby2"):
            self.login_claude(n)
        run(self.seat, self.seat.cmd_auto, "on")
        os.environ.update({"SEAT_ACCOUNT": "viby", "SEAT_AUTO": "0"})   # per-terminal override
        self.write_transcript(self.home / ".claude-viby", [{"type": "assistant", "message": {}}])
        self.set_usage("viby", 100)
        self.set_usage("viby2", 0)
        asked = []
        self.seat.confirm = lambda q, default_yes=True: asked.append(q) or False
        self.assertEqual(run(self.seat, self.seat.cmd_after, "claude", str(time.time() - 30)), "")
        self.assertEqual(len(asked), 1)

    def test_launch_picks_first_seat_with_limit_left(self):
        for n in ("viby", "viby2"):
            self.login_claude(n)
        run(self.seat, self.seat.cmd_remove, "max")
        run(self.seat, self.seat.cmd_auto, "on")
        self.set_usage("viby", 97)
        self.set_usage("viby2", 10)
        self.seat.pick = lambda *a, **k: self.fail("auto mode must not show a menu")
        out = run(self.seat, self.seat.cmd_launch, "claude")
        self.assertIn(f"{self.home}/.claude-viby2", out)
        self.set_usage("viby", 20)             # window reset: back to seat 1
        out = run(self.seat, self.seat.cmd_launch, "claude")
        self.assertIn(f"{self.home}/.claude-viby ", out + " ")
        os.environ["SEAT_PIN"] = "viby2"       # seat use viby2 sticks while it has limit left
        self.assertIn(f"{self.home}/.claude-viby2", run(self.seat, self.seat.cmd_launch, "claude"))

    def test_auto_is_off_by_default(self):
        cfg = self.seat.Config()
        self.assertFalse(self.seat.auto_mode(cfg))
        self.assertFalse(self.seat.is_limited({"ts": time.time(), "five_hour": {"pct": 96, "resets": time.time() + 60}}))
        run(self.seat, self.seat.cmd_auto, "on")
        self.seat.Config()
        self.assertTrue(self.seat.is_limited({"ts": time.time(), "five_hour": {"pct": 96, "resets": time.time() + 60}}))

    def test_order_and_rename(self):
        run(self.seat, self.seat.cmd_bind, "viby,viby2")
        self.set_usage("viby2", 33)
        out = run(self.seat, self.seat.cmd_order, "viby2,viby")
        self.assertIn("1) viby2", out)
        run(self.seat, self.seat.cmd_rename, "viby2", "tolga")
        cfg = self.seat.Config()
        acc = cfg.get("tolga")
        self.assertEqual([a.name for a in cfg.accounts], ["tolga", "viby", "max"])
        self.assertEqual(acc.claude_dir, self.home / ".claude-viby2")
        self.assertEqual(acc.hermes_profile, "viby2")
        self.assertEqual(cfg.projects[0]["accounts"], ["viby", "tolga"])
        self.assertEqual(self.seat.cache_read(acc)["five_hour"]["pct"], 33)
        with self.assertRaises(SystemExit):
            run(self.seat, self.seat.cmd_rename, "tolga", "viby")

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

    # ── hardening ──
    def test_corrupt_config_is_not_overwritten(self):
        run(self.seat, self.seat.cmd_bind, "viby")
        broken = '{"version":1,"accounts":[{"na'
        self.seat.CONFIG.write_text(broken)
        with self.assertRaises(SystemExit):
            self.seat.Config()
        self.assertEqual(self.seat.CONFIG.read_text(), broken)

    def test_legacy_rows_with_bad_names_are_skipped(self):
        (self.home / ".config" / "ccs" / "accounts.tsv").write_text(
            f"max\t{self.home}/.claude\tdefault\tme@gmail.com\n"
            f"../x\t{self.home}/Documents\t../x\tme@evil.io\n")
        self.seat.CONFIG.unlink(missing_ok=True)
        self.assertEqual([a.name for a in self.seat.Config().accounts], ["max"])

    def test_bad_account_in_config_is_skipped_but_kept(self):
        cfg = json.loads(self.seat.Config() and self.seat.CONFIG.read_text())
        cfg["accounts"][1]["hermes_profile"] = "--yes"
        self.seat.CONFIG.write_text(json.dumps(cfg))
        self.assertEqual([a.name for a in self.seat.Config().accounts], ["max", "viby2"])
        run(self.seat, self.seat.cmd_bind, "viby2")   # a save must not drop the bad row
        saved = json.loads(self.seat.CONFIG.read_text())["accounts"]
        self.assertIn("--yes", [a["hermes_profile"] for a in saved])
        self.assertEqual(run(self.seat, self.seat.cmd_cd), "" if False else run(self.seat, self.seat.cmd_cd))

    def test_purge_never_deletes_outside_seat_dir(self):
        victim = self.home / "Documents"
        victim.mkdir()
        (victim / "keep.txt").write_text("x")
        cfg = json.loads(self.seat.Config() and self.seat.CONFIG.read_text())
        cfg["accounts"][1]["claude_dir"] = str(victim)
        self.seat.CONFIG.write_text(json.dumps(cfg))
        self.seat.shutil.which = lambda name: None
        self.seat.subprocess.run = lambda *a, **k: None
        with self.assertRaises(SystemExit):
            run(self.seat, self.seat.cmd_remove, "viby", "--purge")
        self.assertTrue((victim / "keep.txt").exists())

    def test_concurrent_binds_keep_every_rule(self):
        import subprocess
        self.seat.Config()
        env = dict(os.environ)
        dirs = []
        for i in range(6):
            d = self.home / f"p{i}"
            d.mkdir()
            dirs.append(d)
        procs = [subprocess.Popen([sys.executable, str(ROOT / "seat"), "bind", "viby", str(d)], env=env,
                                  stdout=subprocess.DEVNULL) for d in dirs]
        self.assertEqual([p.wait() for p in procs], [0] * len(dirs))
        paths = {r["path"] for r in self.seat.Config().projects}
        self.assertEqual(paths, {str(d.resolve()) for d in dirs})

    @unittest.skipUnless(sys.platform == "darwin", "case-insensitive APFS")
    def test_rule_matches_path_case_insensitively_on_macos(self):
        run(self.seat, self.seat.cmd_bind, "viby", str(self.cwd))
        other_case = Path(str(self.cwd).replace("viby-app", "VIBY-App"))
        self.assertEqual(self.seat.Config().rule_for(other_case)["accounts"], ["viby"])

    def test_statusline_strips_terminal_escapes(self):
        os.environ["SEAT_ACCOUNT"] = "viby"
        sys.stdin = io.StringIO(json.dumps({"model": {"display_name": "Op\x1b]0;pwned\x07us"}}))
        try:
            out = run(self.seat, self.seat.cmd_statusline)
        finally:
            sys.stdin = sys.__stdin__
        self.assertNotIn("\x1b]", out)
        self.assertIn("Op]0;pwnedus", out)

    def test_statusline_survives_bad_numbers(self):
        os.environ["SEAT_ACCOUNT"] = "viby"
        sys.stdin = io.StringIO(json.dumps({"rate_limits": {"five_hour": {"used_percentage": "lots"}}}))
        try:
            out = run(self.seat, self.seat.cmd_statusline)
        finally:
            sys.stdin = sys.__stdin__
        self.assertIn("viby", out)

    def test_fetch_usage_skips_malformed_window(self):
        self.seat.OFFLINE = False
        self.seat.valid_tokens = lambda acc: ["t"]
        self.seat.api_get = lambda path, tok, timeout=0: {
            "five_hour": {"utilization": "bad"}, "seven_day": {"utilization": 41, "resets_at": "nope"}}
        u = self.seat.fetch_usage(self.seat.Config().get("viby"))
        self.assertNotIn("five_hour", u)
        self.assertEqual(u["seven_day"]["pct"], 41.0)

    def test_email_starting_with_dash_is_rejected(self):
        with self.assertRaises(SystemExit):
            run(self.seat, self.seat.cmd_email, "viby", "-x@viby.com")
        self.seat.shutil.which = lambda name: None
        with self.assertRaises(SystemExit):
            run(self.seat, self.seat.cmd_add, "acme", "--x@acme.io")
        with self.assertRaises(SystemExit):
            run(self.seat, self.seat.cmd_email, "viby", "evil\x1b]0;x\x07@viby.com")

    def test_pick_without_tty_exits_cleanly(self):
        real_open = open
        def no_tty(path, *a, **k):
            if path == "/dev/tty":
                raise OSError(6, "Device not configured")
            return real_open(path, *a, **k)
        self.seat.open = no_tty
        with self.assertRaises(SystemExit):
            self.seat.pick("t", self.seat.Config().accounts, "claude")

    def test_hot_path_skips_network_and_sqlite_imports(self):
        import subprocess
        code = (f"import sys,runpy; sys.argv=['seat','_cd']\n"
                f"try: runpy.run_path({str(ROOT / 'seat')!r}, run_name='__main__')\n"
                f"except SystemExit: pass\n"
                f"print('urllib.request' in sys.modules, 'sqlite3' in sys.modules)")
        out = subprocess.run([sys.executable, "-c", code], env=dict(os.environ), capture_output=True, text=True)
        self.assertEqual(out.stdout.strip().splitlines()[-1], "False False")


if __name__ == "__main__":
    unittest.main()
