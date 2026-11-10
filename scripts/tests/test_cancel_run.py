import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis"))
import cancel_run  # noqa: E402


# --------------------------------------------------------------------------
# Fixtures for the diff-vs-baseline detector (RESULTS.md "Refuter"
# 2026-09-13 06:55, "Owed": rewrite detect_acceptance as a diff-vs-
# baseline detector; fix the fixtures to include a 9 -> 9 cancel with a
# late first box).
#
# All fixtures share one baseline shape: idle walk to ANCHOR, attack
# (state 9) with its own hitbox live at ANCHOR+8..ANCHOR+10 (like B's own
# id 256 in B_idle), idle-return to state 0/1 at ANCHOR+IDLE_RETURN_OFFSET
# (like B's own anchor+32).
# --------------------------------------------------------------------------

ANCHOR = 16
IDLE_RETURN_OFFSET = 32  # B_idle's own measured idle-return offset
OWN_BOX_START = 8
OWN_BOX_END = 10
FOLLOW_BOX_OFFSET = 6  # Y's own first-box offset, per Y_idle (RESULTS.md)


def _walk(frames_start, frames_end):
    return [{"frame": f, "state": 1, "ids": [0], "physx": 100}
            for f in range(frames_start, frames_end + 1)]


def _attack_frames(anchor, end_offset, own_box_ids=(256,)):
    """State 9 from anchor..anchor+end_offset-1, own hitbox live at
    anchor+OWN_BOX_START..anchor+OWN_BOX_END."""
    frames = []
    for offset in range(0, end_offset):
        f = anchor + offset
        ids = [0]
        if OWN_BOX_START <= offset <= OWN_BOX_END:
            ids = [0, *own_box_ids]
        frames.append({"frame": f, "state": 9, "ids": ids, "physx": 100})
    return frames


def idle_fixture(anchor=ANCHOR):
    """The attack thrown alone: no follow-up. Own box at anchor+8..+10,
    idle-return at anchor+32."""
    frames = _walk(anchor - 8, anchor - 1)
    frames += _attack_frames(anchor, IDLE_RETURN_OFFSET)
    frames += _walk(anchor + IDLE_RETURN_OFFSET, anchor + IDLE_RETURN_OFFSET + 8)
    return frames


def follow_idle_fixture(anchor=ANCHOR):
    """The follow-up move (e.g. Y) thrown alone: own first box at
    anchor+FOLLOW_BOX_OFFSET (matches Y_idle: id 12 first seen at +6)."""
    frames = _walk(anchor - 8, anchor - 1)
    for offset in range(0, 20):
        f = anchor + offset
        ids = [0, 12] if offset >= FOLLOW_BOX_OFFSET else [0]
        frames.append({"frame": f, "state": 9, "ids": ids, "physx": 100})
    frames += _walk(anchor + 20, anchor + 28)
    return frames


def real_cancel_fixture(anchor, divergence_offset):
    """A real 9->9 cancel with a LATE first box: state stays 9 straight
    through (no dip back to idle), and the follow-up's own hitbox (id
    12) only appears FOLLOW_BOX_OFFSET frames after the cancel actually
    starts -- this is exactly the case the old window-based detector
    missed (RESULTS.md "Refuter": "A cancel goes 9 -> 9 with no dip, and
    a chained Y's first box appears 6+ frames after the cancel start")."""
    frames = _walk(anchor - 8, anchor - 1)
    for offset in range(0, IDLE_RETURN_OFFSET + 20):
        f = anchor + offset
        if offset < OWN_BOX_START or offset > OWN_BOX_END:
            ids = [0]
        else:
            ids = [0, 256]
        if offset >= divergence_offset + FOLLOW_BOX_OFFSET:
            ids = sorted(set(ids) | {12})
        frames.append({"frame": f, "state": 9, "ids": ids, "physx": 100})
    return frames


def press_on_idle_return_fixture(anchor=ANCHOR):
    """A follow-up pressed exactly on the idle-return frame: dropped --
    identical to the idle baseline over the whole shared capture
    (RESULTS.md "Refuter": "a press landing exactly on the idle-return
    frame is dropped")."""
    return idle_fixture(anchor)


def fresh_move_after_idle_return_fixture(anchor, press_offset):
    """Identical to the idle baseline through idle-return, then a fresh
    ordinary move starts at `press_offset` (> idle-return) -- not a
    cancel (RESULTS.md "Refuter": "... the only difference is a fresh
    move after it")."""
    assert press_offset > IDLE_RETURN_OFFSET
    frames = _walk(anchor - 8, anchor - 1)
    frames += _attack_frames(anchor, IDLE_RETURN_OFFSET)
    for offset in range(IDLE_RETURN_OFFSET, press_offset):
        frames.append({"frame": anchor + offset, "state": 1, "ids": [0], "physx": 100})
    for offset in range(press_offset, press_offset + 12):
        frames.append({"frame": anchor + offset, "state": 9, "ids": [0], "physx": 100})
    return frames


def old_k8_first_move_id_fixture(anchor=ANCHOR):
    """The old detector's k=8 first-move-id case: the follow-up is
    pressed at k=8, well inside the FIRST move's own hitbox window
    (anchor+8..+10), and nothing else in the capture ever changes --
    reject. (This is the case the old window-based detector wrongly
    ACCEPTED because it read the first move's own id 256 at anchor+8 as
    follow-up evidence; the diff-vs-baseline detector must reject it
    because the trial is byte-identical to the idle baseline.)"""
    return idle_fixture(anchor)


def own_box_cut_short_fixture(anchor, own_box_end_offset, cut_offset,
                               idle_return_offset, follow_id=12,
                               follow_box_offset=FOLLOW_BOX_OFFSET,
                               own_box_id=270):
    """A move whose OWN recovery hitbox (`own_box_id`, e.g. down B's 270)
    is cut short by the cancel itself -- the "own_vanishes" shape
    (Orchestrator note, RESULTS.md 2026-09-13: down B -> Y's id 270 is
    live anchor+8..+21 in its idle baseline but drops at anchor+21 in
    every down_B_Y_k* trial, `cut_offset` frames before the follow-up's
    own box (`follow_id`) appears at cut_offset + follow_box_offset)."""
    frames = _walk(anchor - 8, anchor - 1)
    for offset in range(0, idle_return_offset + 20):
        ids = [0]
        if OWN_BOX_START <= offset < cut_offset <= own_box_end_offset:
            ids = [0, own_box_id]
        if offset >= cut_offset + follow_box_offset:
            ids = sorted(set(ids) | {follow_id})
        frames.append({"frame": anchor + offset, "state": 9, "ids": ids, "physx": 100})
    return frames


def own_box_baseline_fixture(anchor, own_box_end_offset, idle_return_offset,
                              own_box_id=270):
    """The SAME move thrown alone: its own hitbox stays live through
    `own_box_end_offset` (no follow-up to cut it short)."""
    frames = _walk(anchor - 8, anchor - 1)
    for offset in range(0, idle_return_offset):
        ids = [0, own_box_id] if OWN_BOX_START <= offset <= own_box_end_offset else [0]
        frames.append({"frame": anchor + offset, "state": 9, "ids": ids, "physx": 100})
    frames += _walk(anchor + idle_return_offset, anchor + idle_return_offset + 8)
    return frames


class TestClassifyDivergence(unittest.TestCase):
    """The two divergence shapes (Orchestrator note, RESULTS.md
    2026-09-13, "cancel-start rule for the two divergence shapes")."""

    def test_follow_appears_shape(self):
        baseline = idle_fixture()
        trial = real_cancel_fixture(ANCHOR, divergence_offset=13)
        D, _ = cancel_run.diff_vs_baseline(trial, baseline)
        shape = cancel_run.classify_divergence(trial, baseline, D, {12, 257, 258, 259})
        self.assertEqual(shape, "follow_appears")

    def test_own_vanishes_shape(self):
        baseline = own_box_baseline_fixture(ANCHOR, own_box_end_offset=21,
                                             idle_return_offset=42)
        trial = own_box_cut_short_fixture(ANCHOR, own_box_end_offset=21,
                                           cut_offset=21, idle_return_offset=42)
        D, _ = cancel_run.diff_vs_baseline(trial, baseline)
        self.assertEqual(D, 21)
        shape = cancel_run.classify_divergence(trial, baseline, D, {12, 257, 258, 259})
        self.assertEqual(shape, "own_vanishes")

    def test_ambiguous_shape_when_only_physx_differs(self):
        baseline = [{"frame": 0, "state": 1, "ids": [], "physx": 1},
                    {"frame": 1, "state": 9, "ids": [0], "physx": 100}]
        trial = [{"frame": 0, "state": 1, "ids": [], "physx": 1},
                 {"frame": 1, "state": 9, "ids": [0], "physx": 200}]
        shape = cancel_run.classify_divergence(trial, baseline, 0, {12})
        self.assertEqual(shape, "ambiguous")


def late_box_at_or_after_idle_return_fixture(anchor, box_offset, follow_id=262,
                                              idle_return_offset=IDLE_RETURN_OFFSET):
    """A 9 -> 9 capture (state never dips back to idle, unlike the
    baseline) whose only OTHER divergence before `box_offset` is that
    state staying 9 past `idle_return_offset` -- the whole-capture diff's
    own D therefore lands AT the baseline's idle-return, not before it --
    while the follow-up's own hitbox (`follow_id`) only appears at
    `box_offset` (>= idle_return_offset), recoverable via the box-scan
    fallback (Refuter 09:55, "detect_acceptance ... never scans for the
    follow-up's own ids")."""
    frames = _walk(anchor - 8, anchor - 1)
    for offset in range(0, box_offset + 20):
        ids = [0]
        if OWN_BOX_START <= offset <= OWN_BOX_END:
            ids = [0, 256]
        if offset >= box_offset:
            ids = sorted(set(ids) | {follow_id})
        frames.append({"frame": anchor + offset, "state": 9, "ids": ids, "physx": 100})
    return frames


class TestDiffVsBaselineIncludesPhysy(unittest.TestCase):
    """Refuter 09:55: `diff_vs_baseline` ignored physy; the air routes
    (up_Y -> air_B/air_Y) first diverge on physy alone at +58."""

    def test_physy_only_difference_is_detected(self):
        baseline = [{"frame": 0, "state": 1, "ids": [], "physx": 1, "physy": 1},
                    {"frame": 1, "state": 9, "ids": [0], "physx": 100, "physy": 50}]
        trial = [{"frame": 0, "state": 1, "ids": [], "physx": 1, "physy": 1},
                 {"frame": 1, "state": 9, "ids": [0], "physx": 100, "physy": 58}]
        D, diffs = cancel_run.diff_vs_baseline(trial, baseline)
        self.assertEqual(D, 0)
        self.assertEqual(diffs, ["physy"])

    def test_identical_physy_no_divergence_from_that_field(self):
        baseline = idle_fixture()
        trial = idle_fixture()
        for row in baseline + trial:
            row["physy"] = 7
        D, diffs = cancel_run.diff_vs_baseline(trial, baseline)
        self.assertIsNone(D)


class TestDetectAcceptanceBoxScanFallback(unittest.TestCase):
    """Refuter 09:55 FAIL: detect_acceptance returned "after idle-return"
    as soon as D >= idle-return and never scanned for the follow-up's
    own ids (missed B -> side Y +13, side B -> side Y +23); the same
    omission produced the four "ambiguous / start unknown" rows in grid
    2. Fixed via first_new_follow_box_offset's box-scan fallback."""

    def test_late_diff_field_with_early_box_is_accepted_not_after_idle_return(self):
        # B -> side_Y (Refuter 09:55): the whole-capture diff's own D
        # lands AT idle-return (32, state never dips back to idle), but
        # the follow's own box (262) appears at +34 -- only 2 frames
        # after D, not idle_return + its own 6-frame startup (38) an
        # ordinary buffered press would need. Recovered start = 34 - 6
        # = 28, strictly before idle-return: a real, early cancel the
        # old detector mis-read as "after idle-return".
        baseline = idle_fixture()
        trial = late_box_at_or_after_idle_return_fixture(ANCHOR, box_offset=34)
        evidence = cancel_run.detect_acceptance(
            trial, baseline, "side_Y", follow_box_offset=FOLLOW_BOX_OFFSET)
        self.assertTrue(evidence["accepted"], evidence)
        self.assertFalse(evidence["after_idle_return"])
        self.assertEqual(evidence["follow_start"], 28)

    def test_ordinary_post_recovery_move_is_still_after_idle_return(self):
        # The follow-up's box appears exactly idle_return + its own
        # startup after idle-return -- an ordinary buffered press, not
        # an early cancel -- must stay "after idle-return".
        baseline = idle_fixture()
        trial = late_box_at_or_after_idle_return_fixture(
            ANCHOR, box_offset=IDLE_RETURN_OFFSET + FOLLOW_BOX_OFFSET)
        evidence = cancel_run.detect_acceptance(
            trial, baseline, "side_Y", follow_box_offset=FOLLOW_BOX_OFFSET)
        self.assertFalse(evidence["accepted"])
        self.assertTrue(evidence["after_idle_return"], evidence)

    def test_same_button_followup_box_scan_excludes_first_moves_own_box(self):
        # B -> B: the follow's own ids (256) are identical to the first
        # move's own ids, both live in the idle baseline at +8..+10. The
        # box-scan fallback must not mistake that shared box for follow-
        # up evidence (first_new_follow_box_offset requires the id to be
        # ABSENT from the baseline at that offset).
        baseline = idle_fixture()
        trial = idle_fixture()  # byte-identical: the k=8 union artifact
        evidence = cancel_run.detect_acceptance(
            trial, baseline, "B", follow_box_offset=8)
        self.assertFalse(evidence["accepted"])
        self.assertIsNone(evidence["divergence"])


class TestFirstNewFollowBoxOffset(unittest.TestCase):
    def test_finds_box_absent_from_baseline_at_same_offset(self):
        baseline = idle_fixture()
        trial = real_cancel_fixture(ANCHOR, divergence_offset=13)
        offset = cancel_run.first_new_follow_box_offset(
            trial, baseline, {12, 257, 258, 259})
        self.assertEqual(offset, 13 + FOLLOW_BOX_OFFSET)

    def test_ignores_ids_shared_with_baseline_at_the_same_offset(self):
        baseline = idle_fixture()
        trial = idle_fixture()
        offset = cancel_run.first_new_follow_box_offset(trial, baseline, {256})
        self.assertIsNone(offset)

    def test_none_without_follow_ids(self):
        baseline = idle_fixture()
        trial = real_cancel_fixture(ANCHOR, divergence_offset=13)
        self.assertIsNone(cancel_run.first_new_follow_box_offset(trial, baseline, set()))


class TestWriteSummaryInvocation(unittest.TestCase):
    """Fix list item 4 (RESULTS.md "Refuter" 09:55): the committed
    cancel_windows.md must record the exact --reanalyze --grid
    invocation that produced it."""

    def test_invocation_header_is_written_when_given(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            cancel_run.write_summary(out_dir, [], grid=[4, 8],
                                      invocation="python3 scripts/analysis/cancel_run.py "
                                                 "--reanalyze grid --grid 4 8")
            text = (out_dir / "cancel_windows.md").read_text()
            self.assertIn("Invocation: `python3 scripts/analysis/cancel_run.py "
                          "--reanalyze grid --grid 4 8`", text)

    def test_no_invocation_line_when_omitted(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            cancel_run.write_summary(out_dir, [], grid=[4, 8])
            text = (out_dir / "cancel_windows.md").read_text()
            self.assertNotIn("Invocation:", text)


class TestDiffVsBaseline(unittest.TestCase):
    def test_identical_capture_has_no_divergence(self):
        baseline = idle_fixture()
        trial = idle_fixture()
        D, diffs = cancel_run.diff_vs_baseline(trial, baseline)
        self.assertIsNone(D)
        self.assertIsNone(diffs)

    def test_finds_first_differing_offset_by_ids(self):
        baseline = idle_fixture()
        trial = real_cancel_fixture(ANCHOR, divergence_offset=13)
        D, diffs = cancel_run.diff_vs_baseline(trial, baseline)
        self.assertEqual(D, 13 + FOLLOW_BOX_OFFSET)
        self.assertEqual(diffs, ["ids"])

    def test_ids_compared_as_lists_not_sets(self):
        # {"ids": [0, 0]} vs {"ids": [0]} must be a real difference --
        # a set comparison would silently erase it.
        baseline = [{"frame": 1, "state": 9, "ids": [0, 0], "physx": 1}]
        trial = [{"frame": 1, "state": 9, "ids": [0], "physx": 1}]
        # find_anchor needs a preceding idle frame to anchor on state 9
        baseline = [{"frame": 0, "state": 1, "ids": [], "physx": 1}] + baseline
        trial = [{"frame": 0, "state": 1, "ids": [], "physx": 1}] + trial
        D, diffs = cancel_run.diff_vs_baseline(trial, baseline)
        self.assertEqual(D, 0)
        self.assertEqual(diffs, ["ids"])

    def test_no_anchor_in_either_capture_is_no_divergence(self):
        frames = [{"frame": f, "state": 1, "ids": [], "physx": 0} for f in range(1, 5)]
        D, diffs = cancel_run.diff_vs_baseline(frames, frames)
        self.assertIsNone(D)


class TestFirstBoxOffset(unittest.TestCase):
    def test_follow_up_own_box_offset(self):
        rows = follow_idle_fixture()
        self.assertEqual(cancel_run.first_box_offset(rows, {12}), FOLLOW_BOX_OFFSET)

    def test_none_when_id_never_appears(self):
        rows = idle_fixture()
        self.assertIsNone(cancel_run.first_box_offset(rows, {999}))


class TestDetectAcceptance(unittest.TestCase):
    """The rewritten diff-vs-baseline detector (RESULTS.md "Refuter"
    "Owed"). Four fixtures per the ticket brief: a 9->9 cancel with a
    late first box (accept, D before idle-return), a press on the
    idle-return frame (identical -> reject), a fresh move after idle-
    return ("after idle-return"), and the old k=8 first-move-id case
    (reject)."""

    def test_real_cancel_with_late_first_box_is_accepted(self):
        baseline = idle_fixture()
        trial = real_cancel_fixture(ANCHOR, divergence_offset=13)
        evidence = cancel_run.detect_acceptance(
            trial, baseline, "Y", follow_box_offset=FOLLOW_BOX_OFFSET)
        self.assertTrue(evidence["accepted"], evidence)
        self.assertEqual(evidence["divergence"], 13 + FOLLOW_BOX_OFFSET)
        self.assertLess(evidence["divergence"], evidence["idle_return"])
        self.assertEqual(evidence["follow_start"], 13)
        self.assertFalse(evidence["after_idle_return"])

    def test_press_on_idle_return_frame_is_rejected_as_identical(self):
        baseline = idle_fixture()
        trial = press_on_idle_return_fixture()
        evidence = cancel_run.detect_acceptance(
            trial, baseline, "Y", follow_box_offset=FOLLOW_BOX_OFFSET)
        self.assertFalse(evidence["accepted"])
        self.assertIsNone(evidence["divergence"])
        self.assertFalse(evidence["after_idle_return"])
        self.assertEqual(evidence["reason"], "identical_to_baseline")

    def test_fresh_move_after_idle_return_is_not_a_cancel(self):
        baseline = idle_fixture()
        trial = fresh_move_after_idle_return_fixture(ANCHOR, press_offset=40)
        evidence = cancel_run.detect_acceptance(
            trial, baseline, "Y", follow_box_offset=FOLLOW_BOX_OFFSET)
        self.assertFalse(evidence["accepted"])
        self.assertTrue(evidence["after_idle_return"], evidence)
        self.assertEqual(evidence["divergence"], 40)
        self.assertEqual(evidence["reason"], "after_idle_return")

    def test_old_k8_first_move_id_case_is_rejected(self):
        # The retired window-based detector wrongly ACCEPTED this
        # (RESULTS.md "Debugger"): the follow-up press at k=8 lands
        # inside the FIRST move's own hitbox window, but nothing in the
        # capture actually differs from the idle baseline.
        baseline = idle_fixture()
        trial = old_k8_first_move_id_fixture()
        evidence = cancel_run.detect_acceptance(
            trial, baseline, "B", follow_box_offset=8)
        self.assertFalse(evidence["accepted"])
        self.assertIsNone(evidence["divergence"])

    def test_divergence_at_or_after_idle_return_is_not_accepted(self):
        baseline = idle_fixture()
        trial = real_cancel_fixture(ANCHOR, divergence_offset=IDLE_RETURN_OFFSET)
        evidence = cancel_run.detect_acceptance(trial, baseline, "Y")
        self.assertFalse(evidence["accepted"])

    def test_own_box_cut_short_reports_divergence_itself_as_start(self):
        # down B -> Y (Orchestrator note): the differing field at D is
        # the FIRST move's own box (270) vanishing, not the follow-up's
        # box appearing -- follow_start must be D itself, not D minus
        # the follow-up's own startup lag.
        baseline = own_box_baseline_fixture(ANCHOR, own_box_end_offset=21,
                                             idle_return_offset=42)
        trial = own_box_cut_short_fixture(ANCHOR, own_box_end_offset=21,
                                           cut_offset=21, idle_return_offset=42)
        evidence = cancel_run.detect_acceptance(
            trial, baseline, "Y", follow_box_offset=FOLLOW_BOX_OFFSET)
        self.assertTrue(evidence["accepted"], evidence)
        self.assertEqual(evidence["divergence"], 21)
        self.assertEqual(evidence["shape"], "own_vanishes")
        self.assertEqual(evidence["follow_start"], 21)

    def test_ambiguous_shape_does_not_use_the_follow_appears_formula(self):
        # Found live, jus-atns.4.3 grid 2 (up_B/B/side_B -> up_Y): the
        # first divergence is sometimes an unrelated early id/physx blip,
        # several frames before the follow-up's own hitbox actually
        # appears -- classify_divergence correctly calls this
        # "ambiguous", but detect_acceptance must NOT then apply the
        # follow_appears (D - box_offset) formula to it: that silently
        # reported wrong cancel-start numbers (up_B -> side_Y: +3 instead
        # of the correct +24, recovered by hand from where side_Y's own
        # box 262 actually first appears) before this test was written.
        baseline = [{"frame": 0, "state": 1, "ids": [], "physx": 1},
                    {"frame": 1, "state": 9, "ids": [0, 0], "physx": 100}]
        trial = [{"frame": 0, "state": 1, "ids": [], "physx": 1},
                 {"frame": 1, "state": 9, "ids": [0], "physx": 100},
                 {"frame": 2, "state": 9, "ids": [0], "physx": 100},
                 {"frame": 3, "state": 1, "ids": [0], "physx": 100}]
        baseline += [{"frame": f, "state": 1, "ids": [0], "physx": 100} for f in range(2, 4)]
        evidence = cancel_run.detect_acceptance(
            trial, baseline, "up_Y", follow_box_offset=15)
        self.assertEqual(evidence["shape"], "ambiguous")
        self.assertIsNone(evidence["follow_start"])

    def test_follow_start_is_none_without_box_offset(self):
        baseline = idle_fixture()
        trial = real_cancel_fixture(ANCHOR, divergence_offset=13)
        evidence = cancel_run.detect_acceptance(trial, baseline, "Y")
        self.assertTrue(evidence["accepted"])
        self.assertIsNone(evidence["follow_start"])


class TestDetectIdleReturn(unittest.TestCase):
    def test_idle_return_offset(self):
        frames = idle_fixture()
        self.assertEqual(cancel_run.detect_idle_return(frames, ANCHOR), IDLE_RETURN_OFFSET)

    def test_no_idle_return_found(self):
        frames = [{"frame": f, "state": 9, "ids": []} for f in range(1, 10)]
        self.assertIsNone(cancel_run.detect_idle_return(frames, 0))


class TestFindAnchor(unittest.TestCase):
    def test_first_non_idle_frame(self):
        frames = idle_fixture()
        self.assertEqual(cancel_run.find_anchor(frames), ANCHOR)

    def test_no_anchor_if_always_idle(self):
        frames = _walk(1, 10)
        self.assertIsNone(cancel_run.find_anchor(frames))


class TestAggregateCombo(unittest.TestCase):
    def test_cancel_from_reports_min_follow_start(self):
        baseline = idle_fixture()
        trials = {
            4: real_cancel_fixture(ANCHOR, divergence_offset=13),
            20: real_cancel_fixture(ANCHOR, divergence_offset=20),
        }
        result = cancel_run.aggregate_combo(
            "B", "Y", baseline, trials, [4, 20], follow_box_offset=FOLLOW_BOX_OFFSET)
        self.assertEqual(result["cancel_start"], 13)
        self.assertEqual(result["verdict"], "cancel from +13")

    def test_no_cancel_through_k_when_all_identical(self):
        baseline = idle_fixture()
        trials = {4: idle_fixture(), 8: idle_fixture()}
        result = cancel_run.aggregate_combo("B", "Y", baseline, trials, [4, 8])
        self.assertIsNone(result["cancel_start"])
        self.assertEqual(result["verdict"], "no cancel through +8")

    def test_after_idle_return_only_when_no_real_cancel_found(self):
        baseline = idle_fixture()
        trials = {40: fresh_move_after_idle_return_fixture(ANCHOR, press_offset=40)}
        result = cancel_run.aggregate_combo("B", "Y", baseline, trials, [40])
        self.assertEqual(result["verdict"], "after idle-return only")

    def test_missing_k_renders_as_none_in_per_k(self):
        baseline = idle_fixture()
        result = cancel_run.aggregate_combo("B", "Y", baseline, {}, [4, 8])
        self.assertIsNone(result["per_k"][4])
        self.assertIsNone(result["per_k"][8])


class TestAttachCommandOrder(unittest.TestCase):
    """Fix list item 1 (RESULTS.md "Debugger"): `set logging redirect
    on` must be sent before `set logging enabled on`, or GDB tees every
    per-frame printf to stdout as well as the log file and an unread
    stdout pipe eventually wedges GDB in write()."""

    def test_redirect_precedes_enabled(self):
        commands = [c for c, _wait in cancel_run.attach_commands(Path("/tmp/x.jsonl"))]
        self.assertIn("set logging redirect on", commands)
        self.assertIn("set logging enabled on", commands)
        self.assertLess(commands.index("set logging redirect on"),
                        commands.index("set logging enabled on"))

    def test_enabled_sent_without_waiting_for_a_prompt(self):
        # Once redirect is on, `enabled on`'s own prompt is redirected
        # too -- waiting for it on stdout would hang forever.
        wait_by_command = dict(cancel_run.attach_commands(Path("/tmp/x.jsonl")))
        self.assertFalse(wait_by_command["set logging enabled on"])


class TestEmulatorPausedError(unittest.TestCase):
    def test_paused_text_reply_raises_named_error_not_json_error(self):
        with self.assertRaises(cancel_run.EmulatorPausedError):
            cancel_run._json_prefix(
                "emulator paused (GDB?) — plan frozen, not failed. "
                "Resume the emulator, then `jusemu status`.\n")

    def test_ordinary_json_reply_still_parses(self):
        self.assertEqual(cancel_run._json_prefix('{"ok": true}\n'), {"ok": True})

    def test_other_non_json_reply_still_raises_json_error(self):
        import json
        with self.assertRaises(json.JSONDecodeError):
            cancel_run._json_prefix("not json at all\n")


class TestTrialDirRegex(unittest.TestCase):
    """jus-atns.4.3 grid 2: the old hardcoded `.+_(B|Y)_k\\d+` folder
    regex mis-split directional follow-up names like "side_Y"/"up_Y"
    because they themselves end in "_Y" -- e.g. "Y_side_Y_k4" parsed as
    attack="Y_side", follow="Y" instead of attack="Y", follow="side_Y".
    `_trial_dir_re()` is rebuilt from cancel_plans.ATTACKS/FOLLOWUPS
    (known name lists) so the split is anchored, not purely greedy."""

    def test_plain_b_y_folder_still_parses(self):
        m = cancel_run._TRIAL_DIR_RE.match("B_Y_k4")
        self.assertIsNotNone(m)
        self.assertEqual(m.group("attack"), "B")
        self.assertEqual(m.group("follow"), "Y")
        self.assertEqual(m.group("k"), "4")

    def test_directional_followup_after_plain_y_parses_correctly(self):
        m = cancel_run._TRIAL_DIR_RE.match("Y_side_Y_k4")
        self.assertIsNotNone(m)
        self.assertEqual(m.group("attack"), "Y")
        self.assertEqual(m.group("follow"), "side_Y")
        self.assertEqual(m.group("k"), "4")

    def test_up_y_first_move_air_b_followup_parses_correctly(self):
        m = cancel_run._TRIAL_DIR_RE.match("up_Y_air_B_k8")
        self.assertIsNotNone(m)
        self.assertEqual(m.group("attack"), "up_Y")
        self.assertEqual(m.group("follow"), "air_B")
        self.assertEqual(m.group("k"), "8")

    def test_up_y_first_move_up_y_followup_parses_correctly(self):
        m = cancel_run._TRIAL_DIR_RE.match("up_Y_up_Y_k12")
        self.assertIsNotNone(m)
        self.assertEqual(m.group("attack"), "up_Y")
        self.assertEqual(m.group("follow"), "up_Y")
        self.assertEqual(m.group("k"), "12")

    def test_side_b_attack_not_confused_with_bare_b_followup(self):
        m = cancel_run._TRIAL_DIR_RE.match("side_B_B_k36")
        self.assertIsNotNone(m)
        self.assertEqual(m.group("attack"), "side_B")
        self.assertEqual(m.group("follow"), "B")
        self.assertEqual(m.group("k"), "36")


class TestDiscoverCombos(unittest.TestCase):
    def test_discovers_directional_idle_and_trial_folders(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            grid_dir = Path(tmp)
            for name in ("Y_idle", "up_Y_idle", "side_Y_idle",
                         "Y_side_Y_k4", "Y_up_Y_k8",
                         "up_Y_air_B_k8", "up_Y_air_Y_k8"):
                (grid_dir / name).mkdir()
                (grid_dir / name / "frames.jsonl").write_text("")
            idle_attacks, combos = cancel_run.discover_combos(grid_dir)
            self.assertEqual(idle_attacks, {"Y", "up_Y", "side_Y"})
            self.assertEqual(set(combos), {
                ("Y", "side_Y"), ("Y", "up_Y"),
                ("up_Y", "air_B"), ("up_Y", "air_Y"),
            })
            self.assertEqual(set(combos[("Y", "side_Y")]), {4})
            self.assertEqual(set(combos[("up_Y", "air_B")]), {8})


if __name__ == "__main__":
    unittest.main()
