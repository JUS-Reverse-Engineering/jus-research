import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "emu"))
import cancel_plans  # noqa: E402
import jus_plan  # noqa: E402


def _segments_at(plan, frame):
    """Return the buttons active at `frame`, or None if no segment covers it."""
    for seg in plan["segments"]:
        if seg["from"] <= frame <= seg["to"]:
            return set(seg["buttons"])
    return None


class TestDirectionalFollowupShapes(unittest.TestCase):
    """jus-atns.4.3 grid 2, deliverable 1: side_Y/up_Y hold direction+Y for
    3 frames; air_B/air_Y (as follow-ups) hold just the button for 3 frames
    since up_Y already leaves Kakashi airborne."""

    def test_side_y_followup_is_left_plus_y(self):
        plan = cancel_plans.build_plan("Y", "side_Y", 12)
        follow_frame = cancel_plans.attack_input_frame("Y") + 12
        for f in range(follow_frame, follow_frame + 3):
            self.assertEqual(_segments_at(plan, f), {"LEFT", "Y"}, f"frame {f}")

    def test_up_y_followup_is_up_plus_y(self):
        plan = cancel_plans.build_plan("Y", "up_Y", 20)
        follow_frame = cancel_plans.attack_input_frame("Y") + 20
        for f in range(follow_frame, follow_frame + 3):
            self.assertEqual(_segments_at(plan, f), {"UP", "Y"}, f"frame {f}")

    def test_air_b_followup_is_button_only_no_jump(self):
        plan = cancel_plans.build_plan("up_Y", "air_B", 24)
        follow_frame = cancel_plans.attack_input_frame("up_Y") + 24
        for f in range(follow_frame, follow_frame + 3):
            self.assertEqual(_segments_at(plan, f), {"B"}, f"frame {f}")
        # No "A" (jump) anywhere in the plan: up_Y is already airborne.
        for seg in plan["segments"]:
            self.assertNotIn("A", seg["buttons"])

    def test_air_y_followup_is_button_only_no_jump(self):
        plan = cancel_plans.build_plan("up_Y", "air_Y", 40)
        follow_frame = cancel_plans.attack_input_frame("up_Y") + 40
        for f in range(follow_frame, follow_frame + 3):
            self.assertEqual(_segments_at(plan, f), {"Y"}, f"frame {f}")
        for seg in plan["segments"]:
            self.assertNotIn("A", seg["buttons"])

    def test_up_y_first_move_is_up_plus_y_held_3_frames(self):
        plan = cancel_plans.build_idle_plan("up_Y")
        attack_frame = cancel_plans.attack_input_frame("up_Y")
        self.assertEqual(attack_frame, cancel_plans.WALK_FRAMES)
        for f in range(attack_frame, attack_frame + 3):
            self.assertEqual(_segments_at(plan, f), {"UP", "Y"}, f"frame {f}")

    def test_side_y_standalone_idle_shape(self):
        # side_Y is only ever driven as a follow-up in grid 2, but needs
        # its own idle baseline (re-recorded with this probe) to recover
        # its first-box offset -- same walk-in + press-at-26 shape as any
        # other grounded attack.
        plan = cancel_plans.build_idle_plan("side_Y")
        attack_frame = cancel_plans.attack_input_frame("side_Y")
        self.assertEqual(attack_frame, cancel_plans.WALK_FRAMES)
        for f in range(attack_frame, attack_frame + 3):
            self.assertEqual(_segments_at(plan, f), {"LEFT", "Y"}, f"frame {f}")


class TestNewPlansValidate(unittest.TestCase):
    """Every new plan shape must pass jus_plan.validate_plan with no schema
    or overlap errors, per the ticket's own verification bar for grid 1's
    plan generator."""

    def test_idle_plans_validate(self):
        for attack in ("up_Y", "side_Y"):
            plan = cancel_plans.build_idle_plan(attack)
            jus_plan.validate_plan(plan)  # raises PlanError on failure

    def test_directional_followup_plans_validate(self):
        cases = [
            ("Y", "side_Y"),
            ("Y", "up_Y"),
            ("up_Y", "air_B"),
            ("up_Y", "air_Y"),
        ]
        for attack, follow in cases:
            for k in (8, 24, 56, 90):
                plan = cancel_plans.build_plan(attack, follow, k)
                jus_plan.validate_plan(plan)  # raises PlanError on failure

    def test_small_k_raises_instead_of_unioning(self):
        # Refuter (RESULTS.md 09:55): a k<4 follow-up press used to start
        # before the first move's own PRESS_LEN=3 held frames released,
        # so build_plan unioned both button sets onto the same held
        # frames (an artifact -- side_B_up_Y_k2 merged to B+LEFT+UP+Y and
        # produced a side Y). build_plan must now raise instead of
        # silently producing that artifact.
        for k in (0, 1, 2, 3):
            with self.assertRaises(ValueError):
                cancel_plans.build_plan("Y", "side_Y", k)

    def test_min_followup_k_validates_and_releases_first(self):
        plan = cancel_plans.build_plan("Y", "side_Y", cancel_plans.MIN_FOLLOWUP_K)
        jus_plan.validate_plan(plan)  # raises PlanError on failure
        attack_frame = cancel_plans.attack_input_frame("Y")
        attack_last_press = attack_frame + cancel_plans.PRESS_LEN - 1
        follow_frame = attack_frame + cancel_plans.MIN_FOLLOWUP_K
        # at least one released frame between the first move's own last
        # held frame and the follow-up's first pressed frame
        self.assertGreater(follow_frame, attack_last_press + 1)
        for f in range(attack_last_press + 1, follow_frame):
            self.assertIsNone(_segments_at(plan, f), f"frame {f} should be released")
        self.assertEqual(_segments_at(plan, follow_frame), {"LEFT", "Y"})


class TestMovementFollowups(unittest.TestCase):
    """jus-atns.4.7 grid 3: JUMP/DASH/GUARD follow-ups after B and Y.
    Unlike every FOLLOWUP_BUTTONS entry, each is its own multi-segment
    shape, not a single button set held PRESS_LEN frames."""

    def test_jump_followup_is_a_2_frame_a_press(self):
        plan = cancel_plans.build_plan("B", "JUMP", 4)
        follow_frame = cancel_plans.attack_input_frame("B") + 4
        self.assertEqual(_segments_at(plan, follow_frame), {"A"})
        self.assertEqual(_segments_at(plan, follow_frame + 1), {"A"})
        self.assertIsNone(_segments_at(plan, follow_frame + 2))

    def test_guard_followup_is_down_held_10_frames(self):
        plan = cancel_plans.build_plan("Y", "GUARD", 8)
        follow_frame = cancel_plans.attack_input_frame("Y") + 8
        for f in range(follow_frame, follow_frame + 10):
            self.assertEqual(_segments_at(plan, f), {"DOWN"}, f"frame {f}")
        self.assertIsNone(_segments_at(plan, follow_frame + 10))

    def test_dash_followup_is_tap_gap_tap(self):
        plan = cancel_plans.build_plan("B", "DASH", 4)
        follow_frame = cancel_plans.attack_input_frame("B") + 4
        for f in range(follow_frame, follow_frame + 5):
            self.assertEqual(_segments_at(plan, f), {"LEFT"}, f"tap1 frame {f}")
        for f in range(follow_frame + 5, follow_frame + 10):
            self.assertIsNone(_segments_at(plan, f), f"gap frame {f}")
        for f in range(follow_frame + 10, follow_frame + 15):
            self.assertEqual(_segments_at(plan, f), {"LEFT"}, f"tap2 frame {f}")

    def test_movement_followups_validate(self):
        for follow in ("JUMP", "DASH", "GUARD"):
            for attack in ("B", "Y"):
                for k in cancel_plans.COARSE_GRID:
                    plan = cancel_plans.build_plan(attack, follow, k)
                    jus_plan.validate_plan(plan)

    def test_small_k_raises_for_movement_followups_too(self):
        for follow in ("JUMP", "DASH", "GUARD"):
            with self.assertRaises(ValueError):
                cancel_plans.build_plan("B", follow, 1)

    def test_followup_idle_plan_starts_at_idle_wait_with_no_prior_hold(self):
        for follow, first_buttons in (("JUMP", {"A"}), ("GUARD", {"DOWN"}),
                                       ("DASH", {"LEFT"})):
            plan = cancel_plans.build_followup_idle_plan(follow, idle_wait=10)
            jus_plan.validate_plan(plan)  # raises PlanError on failure
            for f in range(0, 10):
                self.assertIsNone(_segments_at(plan, f), f"{follow} frame {f}")
            self.assertEqual(_segments_at(plan, 10), first_buttons, follow)

    def test_followup_idle_plan_name(self):
        plan = cancel_plans.build_followup_idle_plan("DASH")
        self.assertEqual(plan["name"], "DASH_idle_standalone")

    def test_movement_signature_states_registered(self):
        self.assertEqual(cancel_plans.MOVEMENT_SIGNATURE_STATES["JUMP"], {4, 5, 6})
        self.assertEqual(cancel_plans.MOVEMENT_SIGNATURE_STATES["DASH"], {2})
        self.assertEqual(cancel_plans.MOVEMENT_SIGNATURE_STATES["GUARD"], {3})


class TestFollowupTables(unittest.TestCase):
    def test_new_followups_registered(self):
        for name in ("side_Y", "up_Y", "air_B", "air_Y"):
            self.assertIn(name, cancel_plans.FOLLOWUPS)
            self.assertIn(name, cancel_plans.FOLLOWUP_BUTTONS)
            self.assertIn(name, cancel_plans.FOLLOWUP_IDS)

    def test_followup_ids_match_ticket_facts(self):
        self.assertEqual(cancel_plans.FOLLOWUP_IDS["side_Y"], {262})
        self.assertEqual(cancel_plans.FOLLOWUP_IDS["up_Y"], {264, 265, 266})
        self.assertEqual(cancel_plans.FOLLOWUP_IDS["air_B"], {267})
        self.assertEqual(cancel_plans.FOLLOWUP_IDS["air_Y"], {268})

    def test_up_y_is_a_first_move(self):
        self.assertIn("up_Y", cancel_plans.ATTACKS)


if __name__ == "__main__":
    unittest.main()
