import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit import ManifestError, audit_file, audit_manifest, validate_manifest


def claim(**overrides):
    row = {
        "id": "move-ctor-callers",
        "claim": "The MoveMan constructor has one direct caller.",
        "source": {"path": "docs/confirmed-facts/moves.md", "line": 42},
        "checks": [
            {
                "query": "callers",
                "target": {"overlay": "arm9", "address": "0x02082c34"},
                "expect": {"count": 1},
            }
        ],
        "original_conclusion": "sole caller",
    }
    row.update(overrides)
    return row


class FakeQuery:
    instances = 0
    closes = 0
    field_calls = 0

    def __init__(self):
        type(self).instances += 1

    def callers(self, address, overlay=None):
        return {"query": "callers", "results": [{"source": {"overlay": "arm9", "address": 1}}]}

    def xrefs_to(self, address, overlay=None):
        return {"query": "xrefs_to", "results": []}

    def find_field_writes(self, offset, **scope):
        type(self).field_calls += 1
        return {
            "query": "find_field_writes",
            "truncated": False,
            "results": [
                {"store": {"overlay": "ov6", "address": 0x02157208}, "category": "resolved-offset-only"},
                {"store": {"overlay": "arm9", "address": 0x02000000}, "category": "ranked-candidate"},
            ],
        }

    def decompile(self, address, overlay=None):
        return {"query": "decompile", "completed": True, "c": "memset(obj,0,0x2648);"}

    def close(self):
        type(self).closes += 1


class AuditManifestTests(unittest.TestCase):
    def setUp(self):
        FakeQuery.instances = 0
        FakeQuery.closes = 0
        FakeQuery.field_calls = 0

    def test_rejects_bare_address_and_duplicate_ids(self):
        rows = [claim(), claim()]
        rows[0]["checks"][0]["target"].pop("overlay")
        with self.assertRaisesRegex(ManifestError, "overlay"):
            validate_manifest({"schema_version": 1, "claims": rows, "exclusions": []})

        with self.assertRaisesRegex(ManifestError, "duplicate"):
            validate_manifest({"schema_version": 1, "claims": [claim(), claim()], "exclusions": []})

    def test_one_query_session_audits_all_claims(self):
        manifest = {
            "schema_version": 1,
            "claims": [claim(), claim(id="no-xrefs", checks=[{
                "query": "xrefs_to",
                "target": {"overlay": "arm9", "address": "0x02000000"},
                "expect": {"count": 0},
            }])],
            "exclusions": [],
        }

        result = audit_manifest(manifest, query_factory=FakeQuery)

        self.assertEqual(FakeQuery.instances, 1)
        self.assertEqual(FakeQuery.closes, 1)
        self.assertEqual([row["verdict"] for row in result["claims"]], ["confirmed", "confirmed"])

    def test_truncated_or_unsupported_evidence_is_inconclusive(self):
        class Truncated(FakeQuery):
            def callers(self, address, overlay=None):
                return {"query": "callers", "results": [], "truncated": True}

        manifest = {"schema_version": 1, "claims": [claim()], "exclusions": []}
        result = audit_manifest(manifest, query_factory=Truncated)
        self.assertEqual(result["claims"][0]["verdict"], "inconclusive")

        unsupported = claim(checks=[{
            "query": "semantic_reachability",
            "target": {"overlay": "arm9", "address": "0x02082c34"},
            "expect": {"count": 0},
        }])
        result = audit_manifest(
            {"schema_version": 1, "claims": [unsupported], "exclusions": []},
            query_factory=FakeQuery,
        )
        self.assertEqual(result["claims"][0]["verdict"], "inconclusive")

    def test_mismatched_cardinality_is_contradicted(self):
        result = audit_manifest(
            {"schema_version": 1, "claims": [claim(checks=[{
                "query": "xrefs_to",
                "target": {"overlay": "arm9", "address": "0x02000000"},
                "expect": {"count": 1},
            }])], "exclusions": []},
            query_factory=FakeQuery,
        )
        self.assertEqual(result["claims"][0]["verdict"], "contradicted")

    def test_field_write_checks_can_filter_structured_results(self):
        row = claim(checks=[{
            "query": "find_field_writes",
            "field": {"offset": "0x175"},
            "where": {"store.overlay": "ov6", "store.address": "0x02157208"},
            "expect": {"count": 1},
        }])
        result = audit_manifest(
            {"schema_version": 1, "claims": [row], "exclusions": []},
            query_factory=FakeQuery,
        )
        self.assertEqual(result["claims"][0]["verdict"], "confirmed")

    def test_decompile_contains_and_manual_review(self):
        row = claim(checks=[{
            "query": "decompile",
            "target": {"overlay": "arm9", "address": "0x02082a38"},
            "expect": {"contains": ["memset(obj,0,0x2648)"]},
        }])
        result = audit_manifest(
            {"schema_version": 1, "claims": [row], "exclusions": []},
            query_factory=FakeQuery,
        )
        self.assertEqual(result["claims"][0]["verdict"], "confirmed")

        row["checks"][0]["expect"] = {"review": "dominance requires manual inspection"}
        result = audit_manifest(
            {"schema_version": 1, "claims": [row], "exclusions": []},
            query_factory=FakeQuery,
        )
        self.assertEqual(result["claims"][0]["verdict"], "inconclusive")
        self.assertEqual(result["claims"][0]["evidence"][0]["evidence"]["query"], "decompile")

    def test_audit_file_writes_deterministic_json(self):
        manifest = {"schema_version": 1, "claims": [claim()], "exclusions": []}
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            output = Path(directory) / "output.json"
            source.write_text(json.dumps(manifest), encoding="utf-8")

            audit_file(source, output, query_factory=FakeQuery)

            payload = output.read_text(encoding="utf-8")
            self.assertTrue(payload.endswith("\n"))
            saved = json.loads(payload)
            self.assertEqual(saved["claims"][0]["verdict"], "confirmed")
            self.assertEqual(saved["claims"][0]["evidence"][0]["evidence"]["result_count"], 1)

    def test_query_failure_is_inconclusive_and_does_not_abort_sweep(self):
        class Failing(FakeQuery):
            def callers(self, address, overlay=None):
                if address == 0x02000001:
                    raise ValueError("not mapped")
                return super().callers(address, overlay)

        bad = claim(checks=[{
            "query": "callers",
            "target": {"overlay": "arm9", "address": "0x02000001"},
            "expect": {"count": 0},
        }])
        result = audit_manifest(
            {"schema_version": 1, "claims": [bad, claim(id="still-runs")], "exclusions": []},
            query_factory=Failing,
        )
        self.assertEqual([row["verdict"] for row in result["claims"]], ["inconclusive", "confirmed"])
        self.assertIn("not mapped", result["claims"][0]["evidence"][0]["reason"])

    def test_identical_queries_are_reused_within_one_session(self):
        check = {"query": "find_field_writes", "field": {"offset": "0x68"}, "expect": {"review": "manual"}}
        result = audit_manifest(
            {"schema_version": 1, "claims": [claim(checks=[check]), claim(id="same", checks=[check])], "exclusions": []},
            query_factory=FakeQuery,
        )
        self.assertEqual(FakeQuery.field_calls, 1)
        self.assertEqual([row["verdict"] for row in result["claims"]], ["inconclusive", "inconclusive"])


if __name__ == "__main__":
    unittest.main()
