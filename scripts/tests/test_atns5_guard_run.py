import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis"))
import atns5_guard_run as guard_run  # noqa: E402


def _guard_hold_rows(button_up, guard_start=1, arm_frame=3, drain_end=9, end=15):
    """Build a small fixture log for a guard hold from frame 0 to
    `button_up`-1: state==3 and guard_bit==1 while held (guard_start..
    button_up), lock arms to 6 at `arm_frame` and drains 1/frame to 0 at
    `drain_end`, everything returns to idle (state 0, guard_bit 0) at
    button_up+1 (matches guard-sp.md §0.8's "+1 after release" shape)."""
    rows = []
    for f in range(0, end):
        if guard_start <= f <= button_up:
            state, guard_bit = 3, 1
        else:
            state, guard_bit = 0, 0
        if f < arm_frame:
            lock = 0
        else:
            lock = max(0, 6 - (f - arm_frame))
        in_down = 1 if f < button_up else 0
        rows.append({"frame": f, "state": state, "state2": 0, "lock": lock,
                      "guard_bit": guard_bit, "blocked_latch": 0,
                      "in_down": in_down, "in_x80": 0, "in_x100": 0,
                      "hp1": 160, "hp2": 160, "ids": []})
    return rows


class NormalizeRowTest(unittest.TestCase):
    """jus-wmqi.2 probe rows log `recs` ([record, id] pairs) instead of `ids`."""

    def test_builds_ids_from_recs(self):
        row = guard_run.normalize_row({"frame": 1, "recs": [[11, 256], [12, 257]]})
        self.assertEqual(row["ids"], [256, 257])

    def test_keeps_existing_ids(self):
        row = guard_run.normalize_row({"frame": 1, "ids": [5], "recs": [[11, 256]]})
        self.assertEqual(row["ids"], [5])

    def test_old_rows_unchanged(self):
        row = guard_run.normalize_row({"frame": 1, "ids": []})
        self.assertEqual(row, {"frame": 1, "ids": []})


class FindStateClearFrameTest(unittest.TestCase):
    def test_finds_first_frame_after_release_leaving_guard_state(self):
        rows = _guard_hold_rows(button_up=1, end=15)
        # state stays 3 through frame 1 (button_up), clears at frame 2.
        self.assertEqual(guard_run.find_state_clear_frame(rows, after_frame=1), 2)

    def test_returns_none_when_never_clears(self):
        rows = [{"frame": f, "state": 3} for f in range(0, 5)]
        self.assertIsNone(guard_run.find_state_clear_frame(rows, after_frame=1))


class FindGuardBitClearFrameTest(unittest.TestCase):
    def test_finds_first_frame_bit_drops_after_having_been_set(self):
        rows = _guard_hold_rows(button_up=1, end=15)
        self.assertEqual(guard_run.find_guard_bit_clear_frame(rows, after_frame=1), 2)

    def test_none_when_bit_was_never_set(self):
        rows = [{"frame": f, "guard_bit": 0} for f in range(0, 5)]
        self.assertIsNone(guard_run.find_guard_bit_clear_frame(rows, after_frame=1))


class FindLockZeroFrameTest(unittest.TestCase):
    def test_finds_zero_after_arming(self):
        rows = _guard_hold_rows(button_up=30, arm_frame=3, end=40)
        self.assertEqual(guard_run.find_lock_zero_frame(rows), 9)

    def test_none_when_never_armed(self):
        rows = [{"frame": f, "lock": 0} for f in range(0, 5)]
        self.assertIsNone(guard_run.find_lock_zero_frame(rows))


class FindAcceptanceFrameTest(unittest.TestCase):
    def test_finds_state_nine_at_or_after_press(self):
        rows = [{"frame": f, "state": 9 if f >= 5 else 0} for f in range(0, 10)]
        self.assertEqual(guard_run.find_acceptance_frame(rows, press_frame=2), 5)

    def test_none_when_dropped(self):
        rows = [{"frame": f, "state": 0} for f in range(0, 10)]
        self.assertIsNone(guard_run.find_acceptance_frame(rows, press_frame=2))


class FindFirstHitboxTest(unittest.TestCase):
    def test_finds_first_nonempty_ids_at_or_after(self):
        rows = [{"frame": f, "ids": [256] if f >= 6 else []} for f in range(0, 10)]
        frame, ids = guard_run.find_first_hitbox(rows, after_frame=3)
        self.assertEqual(frame, 6)
        self.assertEqual(ids, [256])

    def test_none_when_never_live(self):
        rows = [{"frame": f, "ids": []} for f in range(0, 10)]
        self.assertEqual(guard_run.find_first_hitbox(rows, after_frame=0), (None, None))

    def test_ignores_id_persistently_live_before_after_frame(self):
        # jus-atns.5 RESULTS.md/Refuter finding: id 6 is a standing
        # body/hurtbox record, live on every frame including well before
        # any attack -- `find_first_hitbox` must not report it as "the
        # first hitbox". Padding zeros in the `ids` list are also not
        # real ids and must be ignored the same way.
        rows = [{"frame": f, "ids": [6, 0, 0] if f < 8 else [6, 0, 256, 0]}
                for f in range(0, 12)]
        frame, ids = guard_run.find_first_hitbox(rows, after_frame=2)
        self.assertEqual(frame, 8)
        self.assertEqual(ids, [256])

    def test_none_when_only_persistently_live_id_present(self):
        rows = [{"frame": f, "ids": [6, 0, 0]} for f in range(0, 10)]
        self.assertEqual(guard_run.find_first_hitbox(rows, after_frame=0), (None, None))

    def test_baseline_taken_at_or_before_after_frame_not_frame_zero(self):
        # id 6 goes live only at frame 3 (still before `after_frame`=5,
        # e.g. an attacker who was already mid-startup when the window of
        # interest begins) -- it must still be treated as baseline noise,
        # not reported as a "new" hitbox at frame 5.
        rows = [{"frame": f, "ids": [] if f < 3 else ([6] if f < 9 else [6, 256])}
                for f in range(0, 12)]
        frame, ids = guard_run.find_first_hitbox(rows, after_frame=5)
        self.assertEqual(frame, 9)
        self.assertEqual(ids, [256])

    def test_delta_zero_blind_spot_pinned(self):
        # Documented gap (jus-atns.5 fix pass, module docstring item 5 and
        # this function's own docstring): a hitbox already live ON
        # `after_frame` itself is folded into the baseline (the baseline
        # scan's break condition is `frame > after_frame`, not `>=`), so
        # it can never be reported as "new" -- even though it is a real
        # hitbox on that exact frame. This pins the CURRENT behavior (a
        # false None/blind spot at delta 0), not a desired one; a future
        # fix that closes this gap should update this test, not silently
        # break it.
        rows = [{"frame": f, "ids": [256] if f >= 5 else []} for f in range(0, 10)]
        # The id goes live AT after_frame=5 itself.
        frame, ids = guard_run.find_first_hitbox(rows, after_frame=5)
        self.assertEqual((frame, ids), (None, None))
        # One frame later (after_frame=4), the same id is a genuine
        # delta-+1 "new" hitbox and IS detected -- confirms the gap is
        # specific to delta 0, not a general failure to see id 256.
        frame, ids = guard_run.find_first_hitbox(rows, after_frame=4)
        self.assertEqual(frame, 5)
        self.assertEqual(ids, [256])


class FindFirstContactTest(unittest.TestCase):
    def test_finds_first_hp2_drop(self):
        rows = [{"frame": f, "hp2": 160 if f < 8 else 153} for f in range(0, 12)]
        self.assertEqual(guard_run.find_first_contact(rows), 8)

    def test_none_when_hp2_never_drops(self):
        rows = [{"frame": f, "hp2": 160} for f in range(0, 12)]
        self.assertIsNone(guard_run.find_first_contact(rows))


class SummarizeTrialTest(unittest.TestCase):
    def test_guard_only_trial_reports_flag_clear_as_max_of_the_two(self):
        rows = _guard_hold_rows(button_up=1, end=15)
        summary = guard_run.summarize_trial(rows, {"button_up": 1, "b_press": None})
        self.assertEqual(summary["state_clear"], 2)
        self.assertEqual(summary["guard_bit_clear"], 2)
        self.assertEqual(summary["lock_zero"], 9)
        self.assertEqual(summary["flag_clear"], 2)
        self.assertIsNone(summary["acceptance"])

    def test_attack_trial_reports_acceptance_and_first_hitbox(self):
        rows = [{"frame": f, "state": 9 if f >= 3 else 0, "state2": 0,
                  "lock": 0, "guard_bit": 0, "blocked_latch": 0,
                  "in_down": 0, "in_x80": 1 if 0 <= f <= 2 else 0,
                  "hp1": 160, "hp2": 160, "ids": [256] if f >= 6 else []}
                for f in range(0, 12)]
        summary = guard_run.summarize_trial(rows, {"button_up": None, "b_press": 0})
        self.assertEqual(summary["acceptance"], 3)
        self.assertEqual(summary["first_hitbox_frame"], 6)
        self.assertEqual(summary["first_hitbox_ids"], [256])

    def test_dropped_press_reports_the_string_dropped(self):
        rows = [{"frame": f, "state": 3, "state2": 0, "lock": 0,
                  "guard_bit": 1, "blocked_latch": 0, "in_down": 1,
                  "in_x80": 1 if 2 <= f <= 4 else 0,
                  "hp1": 160, "hp2": 160,
                  "ids": []} for f in range(0, 10)]
        summary = guard_run.summarize_trial(rows, {"button_up": None, "b_press": 2})
        self.assertEqual(summary["acceptance"], "dropped")


class PlanBuildersTest(unittest.TestCase):
    def test_tap_or_hold_b_plan_places_b_press_at_release_plus_k(self):
        plan, meta = guard_run.tap_or_hold_b_plan("tap_B_4", "fixture", hold_frames=1, k=4)
        self.assertEqual(meta["button_up"], 1)
        self.assertEqual(meta["b_press"], 5)
        b_segment = next(s for s in plan["segments"] if "B" in s["buttons"])
        self.assertEqual(b_segment["from"], 5)

    def test_guard_only_plan_holds_down_for_the_full_span(self):
        plan, meta = guard_run.guard_only_plan("hold30_only", "fixture", hold_frames=30)
        self.assertEqual(meta["button_up"], 30)
        down_segment = plan["segments"][0]
        self.assertEqual((down_segment["from"], down_segment["to"]), (0, 29))


class ReadNewLinesTest(unittest.TestCase):
    def test_missing_file_returns_empty_and_same_offset(self):
        rows, offset = guard_run.read_new_lines(Path("/tmp/does-not-exist-atns5.jsonl"), 5)
        self.assertEqual(rows, [])
        self.assertEqual(offset, 5)

    def test_returns_only_lines_after_offset_and_advances_it(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "log.jsonl"
            p.write_text(
                "\n".join(json.dumps({"type": "frame", "frame": i}) for i in range(5))
                + "\n",
                encoding="utf-8",
            )
            rows, offset = guard_run.read_new_lines(p, 0)
            self.assertEqual([r["frame"] for r in rows], [0, 1, 2, 3, 4])
            self.assertEqual(offset, 5)

            # append 3 more lines; a second call with the offset returned
            # above must see only the NEW lines, not the first 5 again.
            with p.open("a", encoding="utf-8") as fh:
                for i in range(5, 8):
                    fh.write(json.dumps({"type": "frame", "frame": i}) + "\n")
            rows2, offset2 = guard_run.read_new_lines(p, offset)
            self.assertEqual([r["frame"] for r in rows2], [5, 6, 7])
            self.assertEqual(offset2, 8)

    def test_skips_blank_lines_and_non_frame_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "log.jsonl"
            p.write_text(
                "\n".join([
                    json.dumps({"type": "frame", "frame": 0}),
                    "",
                    json.dumps({"type": "other", "frame": 1}),
                    json.dumps({"type": "frame", "frame": 2}),
                ]) + "\n",
                encoding="utf-8",
            )
            rows, offset = guard_run.read_new_lines(p, 0)
            self.assertEqual([r["frame"] for r in rows], [0, 2])
            # offset advances by RAW line count, not filtered row count --
            # callers rely on this to avoid re-reading skipped lines.
            self.assertEqual(offset, 4)

    def test_fills_ids_from_recs_on_wmqi2_probe_rows(self):
        # A raw line in the jus-wmqi.2 probe format has `recs` but no `ids`.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "log.jsonl"
            p.write_text(
                '{"type":"frame","frame":7,"state":9,"recs":[[11,256],[13,262]]}\n',
                encoding="utf-8",
            )
            rows, offset = guard_run.read_new_lines(p, 0)
            self.assertEqual(offset, 1)
            self.assertEqual(rows[0]["ids"], [256, 262])


class RunOneNoTrimTest(unittest.TestCase):
    """jus-atns.5 RESULTS.md 'the driven-frame trim' / Refuter item 6:
    Runner.run_one() must keep EVERY newly appended row rather than
    trimming to the plan's own reported `frames` count -- the real
    button-press edge can land well inside a large leading run of idle
    frames that a last-N trim would discard."""

    def test_run_one_keeps_all_new_lines_not_trimmed_to_reported_frames(self):
        with tempfile.TemporaryDirectory() as d:
            raw_log = Path(d) / "raw.log"
            out_dir = Path(d) / "out"
            runner = guard_run.Runner(gdb_binary="unused", raw_log=raw_log,
                                       holder="test", out_dir=out_dir, launch=False)
            runner.gdb = None  # no live GDB session in this test
            runner.offset = 0
            runner._load_state = lambda slot: {"ok": True}

            total_lines = 50
            reported_frames = 5  # far fewer than total_lines

            def fake_jusemu(*args, **kwargs):
                if args and args[0] == "state":
                    return {"ok": True}
                # simulate the emulator run: the raw log now has
                # `total_lines` frame rows, but the plan reports far
                # fewer "frames" than that -- run_one must not use this
                # number to trim.
                raw_log.parent.mkdir(parents=True, exist_ok=True)
                with raw_log.open("w", encoding="utf-8") as fh:
                    for i in range(total_lines):
                        fh.write(json.dumps({"type": "frame", "frame": i}) + "\n")
                return {"ok": True, "frames": reported_frames}

            original_jusemu = guard_run.jusemu
            guard_run.jusemu = fake_jusemu
            try:
                rows, result = runner.run_one(
                    {"name": "t", "load_state": "fixture", "segments": [], "watches": []},
                    ipc_root=Path(d) / "ipc",
                )
            finally:
                guard_run.jusemu = original_jusemu

            self.assertEqual(result["frames"], reported_frames)
            self.assertEqual(len(rows), total_lines)
            # rows are renumbered from 1, with the original frame kept
            # separately in raw_frame (per run_one's own contract).
            self.assertEqual(rows[0]["frame"], 1)
            self.assertEqual(rows[0]["raw_frame"], 0)
            self.assertEqual(rows[-1]["frame"], total_lines)
            self.assertEqual(rows[-1]["raw_frame"], total_lines - 1)


class RunOnePlanRootTest(unittest.TestCase):
    """run_one() writes its plan file under the injected IPC root, never
    under the live emulator root, and hands that exact path to jusemu."""

    def test_plan_lands_under_injected_root_and_is_passed_to_jusemu(self):
        with tempfile.TemporaryDirectory() as d:
            ipc = Path(d) / "ipc"
            runner = guard_run.Runner(gdb_binary="unused", raw_log=Path(d) / "raw.log",
                                       holder="test", out_dir=Path(d) / "out", launch=False)
            runner.gdb = None
            runner.offset = 0
            runner._load_state = lambda slot: {"ok": True}
            seen = []

            def fake_jusemu(*args, **kwargs):
                seen.append(args)
                return {"ok": True, "frames": 0}

            original_jusemu = guard_run.jusemu
            guard_run.jusemu = fake_jusemu
            try:
                runner.run_one({"name": "t", "load_state": "fixture", "segments": [],
                                "watches": []}, ipc_root=ipc)
            finally:
                guard_run.jusemu = original_jusemu

            plan_path = ipc / "atns5_plan_t.json"
            self.assertTrue(plan_path.is_file())
            self.assertEqual(seen[-1], ("run", str(plan_path)))


class RetryUnlinkRootTest(unittest.TestCase):
    """jusemu()'s stale-pending retry clears <root>/cmd/pending.json for the
    injected root only. A sibling root's pending.json must be left alone."""

    def test_retry_unlinks_pending_under_injected_root_only(self):
        import types
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "ipc"
            (root / "cmd").mkdir(parents=True)
            pending = root / "cmd" / "pending.json"
            pending.write_text('{"id": 1, "epoch": 1}', encoding="utf-8")
            sibling = Path(d) / "other" / "cmd" / "pending.json"
            sibling.parent.mkdir(parents=True)
            sibling.write_text('{"id": 9, "epoch": 9}', encoding="utf-8")
            calls = [types.SimpleNamespace(returncode=1, stdout="",
                                           stderr="a command is pending"),
                     types.SimpleNamespace(returncode=0, stdout='{"ok": true}',
                                           stderr="")]
            with mock.patch.object(guard_run.subprocess, "run", side_effect=calls), \
                    mock.patch.object(guard_run, "_bridge_is_paused", return_value=False):
                result = guard_run.jusemu("run", "p.json", ipc_root=root)
            self.assertEqual(result, {"ok": True})
            self.assertFalse(pending.exists())
            self.assertTrue(sibling.exists())


if __name__ == "__main__":
    unittest.main()
