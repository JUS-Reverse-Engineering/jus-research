#!/usr/bin/env python3
"""Check the held-out success criteria for the three follow-up trials."""

import json
from pathlib import Path


ROOT = Path(__file__).parent


def load(trial: str, name: str) -> dict:
    return json.loads((ROOT / trial / name).read_text())


landing_ts = load("landing-lag-generalization-2026-09-16", "typesafe-response.json")["answers"]
landing_luna = load("landing-lag-generalization-2026-09-16", "ordinary-reviewer-response.json")
assert landing_ts["claim_status"]["choice"] in {
    "unsupported_within_run_fit",
    "contradicted_by_holdout",
}
assert landing_ts["primary_issue"]["choice"] == "input_not_independent"
assert landing_ts["preserves_measurements"]["noul"] >= 0.8
assert landing_luna["verdict"] in {"contradicted", "unsupported_within_run_fit"}

gate_ts = load("mode-gate-causality-2026-09-16", "typesafe-response.json")["answers"]
gate_luna = load("mode-gate-causality-2026-09-16", "ordinary-reviewer-response.json")
assert gate_ts["causal_status"]["choice"] == "underdetermined_missing_execution"
assert gate_ts["primary_issue"]["choice"] == "failing_mode_did_not_reach_check"
assert gate_ts["preserves_observations"]["noul"] >= 0.8
assert gate_luna["verdict"] == "underdetermined"

projectile_ts = load("projectile-matched-causality-2026-09-16", "typesafe-response.json")["answers"]
projectile_luna = load("projectile-matched-causality-2026-09-16", "ordinary-reviewer-response.json")
assert projectile_ts["case_a_status"]["choice"] == "underdetermined_missing_causal_observation"
assert projectile_ts["case_a_basis"]["choice"] == "missing_causal_variable"
assert projectile_ts["case_a_preserves_teardown"]["noul"] >= 0.8
assert projectile_ts["case_a_scope"]["choice"] == "no_causal_scope"
assert projectile_ts["case_b_status"]["choice"] in {"supported", "supported_with_scope_caveat"}
assert projectile_ts["case_b_basis"]["choice"] == "direct_variable_to_teardown_link"
assert projectile_ts["case_b_preserves_teardown"]["noul"] >= 0.8
assert projectile_ts["case_b_scope"]["choice"] == "projectile_subsystem"
assert projectile_luna["case_a"]["verdict"] == "underdetermined"
assert projectile_luna["case_b"]["verdict"] in {"supported", "supported_with_scope_caveat"}

print("PASS: 3/3 trials; TypeSafe and Luna met every held-out criterion")
