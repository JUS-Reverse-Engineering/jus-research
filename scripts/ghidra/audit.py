#!/usr/bin/env python3
"""Validate and execute the G2 negative-claim audit manifest."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


VERDICTS = {"confirmed", "contradicted", "inconclusive"}
ADDRESS_QUERIES = {
    "callers": "callers",
    "callees": "callees",
    "decompile": "decompile",
    "xrefs_to": "xrefs_to",
    "xrefs_from": "xrefs_from",
}


class ManifestError(ValueError):
    pass


def validate_manifest(manifest):
    if manifest.get("schema_version") != 1:
        raise ManifestError("schema_version must be 1")
    claims = manifest.get("claims")
    if not isinstance(claims, list):
        raise ManifestError("claims must be a list")
    seen = set()
    for row in claims:
        row_id = row.get("id")
        if not row_id:
            raise ManifestError("every claim needs an id")
        if row_id in seen:
            raise ManifestError(f"duplicate claim id: {row_id}")
        seen.add(row_id)
        source = row.get("source", {})
        if not source.get("path") or not isinstance(source.get("line"), int):
            raise ManifestError(f"{row_id}: source path and line are required")
        checks = row.get("checks")
        if not isinstance(checks, list) or not checks:
            raise ManifestError(f"{row_id}: at least one check is required")
        for check in checks:
            if check.get("query") == "find_field_writes":
                offset = check.get("field", {}).get("offset")
                if not isinstance(offset, str) or not offset.lower().startswith("0x"):
                    raise ManifestError(f"{row_id}: field offset must be a hexadecimal string")
            else:
                target = check.get("target", {})
                if not target.get("overlay"):
                    raise ManifestError(f"{row_id}: every address needs an overlay")
                address = target.get("address")
                if not isinstance(address, str) or not address.lower().startswith("0x"):
                    raise ManifestError(f"{row_id}: address must be a hexadecimal string")
            expect = check.get("expect", {})
            if "count" in expect and (not isinstance(expect["count"], int) or expect["count"] < 0):
                raise ManifestError(f"{row_id}: expect.count must be non-negative")
            if not any(key in expect for key in ("count", "contains", "review")):
                raise ManifestError(f"{row_id}: expect needs count, contains, or review")
    return manifest


def _run_check(query, check, response_cache):
    review = check["expect"].get("review")
    cache_key = json.dumps(
        {key: check.get(key) for key in ("query", "target", "field")},
        sort_keys=True,
    )
    if check["query"] == "find_field_writes":
        field = check["field"]
        if cache_key not in response_cache:
            response_cache[cache_key] = query.find_field_writes(
                int(field["offset"], 0),
                base_hint=int(field["base_hint"], 0) if field.get("base_hint") else None,
                overlay=field.get("overlay"),
                function=int(field["function"], 0) if field.get("function") else None,
                max_results=field.get("max_results", 500),
            )
        response = response_cache[cache_key]
        if review:
            return {"status": "inconclusive", "reason": review, "evidence": response}
        return _check_response(response, check)
    method_name = ADDRESS_QUERIES.get(check["query"])
    if method_name is None:
        return {"status": "inconclusive", "reason": f"unsupported query: {check['query']}"}
    target = check["target"]
    if cache_key not in response_cache:
        response_cache[cache_key] = getattr(query, method_name)(int(target["address"], 0), target["overlay"])
    response = response_cache[cache_key]
    if review:
        return {"status": "inconclusive", "reason": review, "evidence": response}
    if check["query"] == "decompile":
        if not response.get("completed"):
            return {"status": "inconclusive", "reason": "decompilation did not complete", "evidence": response}
        needles = check["expect"].get("contains", [])
        missing = [needle for needle in needles if needle not in response.get("c", "")]
        return {"status": "confirmed" if not missing else "contradicted", "missing": missing, "evidence": response}
    return _check_response(response, check)


def _nested(row, path):
    value = row
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _same(actual, expected):
    if isinstance(actual, int) and isinstance(expected, str) and expected.lower().startswith("0x"):
        return actual == int(expected, 0)
    return actual == expected


def _check_response(response, check):
    if response.get("truncated"):
        return {"status": "inconclusive", "reason": "query result was truncated", "evidence": response}
    rows = response.get("results", [])
    where = check.get("where", {})
    rows = [row for row in rows if all(_same(_nested(row, key), value) for key, value in where.items())]
    actual = len(rows)
    expected = check["expect"]["count"]
    return {
        "status": "confirmed" if actual == expected else "contradicted",
        "actual_count": actual,
        "expected_count": expected,
        "evidence": response,
    }


def audit_manifest(manifest, query_factory=None):
    validate_manifest(manifest)
    if query_factory is None:
        from analysis import GhidraQuery

        query_factory = GhidraQuery
    result = deepcopy(manifest)
    query = query_factory()
    response_cache = {}
    try:
        for row in result["claims"]:
            evidence = []
            for check in row["checks"]:
                try:
                    evidence.append(_run_check(query, check, response_cache))
                except Exception as exc:
                    evidence.append({"status": "inconclusive", "reason": f"{type(exc).__name__}: {exc}"})
            statuses = {item["status"] for item in evidence}
            if "contradicted" in statuses:
                verdict = "contradicted"
            elif "inconclusive" in statuses:
                verdict = "inconclusive"
            else:
                verdict = "confirmed"
            row["verdict"] = verdict
            row["evidence"] = evidence
        result["tooling"] = deepcopy(getattr(query, "metadata", {}))
        result["generated_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        query.close()
    return result


def _compact_response(response):
    keep = {
        key: deepcopy(response[key])
        for key in ("query", "target", "source", "offset", "base_hint", "scope", "truncated", "completed", "function", "c")
        if key in response
    }
    rows = response.get("results")
    if rows is not None:
        keep["result_count"] = len(rows)
        keep["results"] = [{key: deepcopy(value) for key, value in row.items() if key != "slice"} for row in rows]
    return keep


def compact_audit_result(result):
    compact = deepcopy(result)
    for row in compact["claims"]:
        for item in row.get("evidence", []):
            if "evidence" in item:
                item["evidence"] = _compact_response(item["evidence"])
    return compact


def audit_file(source, output, query_factory=None):
    source = Path(source)
    output = Path(output)
    manifest = json.loads(source.read_text(encoding="utf-8"))
    result = compact_audit_result(audit_manifest(manifest, query_factory=query_factory))
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = audit_file(args.manifest, args.output)
    counts = {verdict: 0 for verdict in sorted(VERDICTS)}
    for row in result["claims"]:
        counts[row["verdict"]] += 1
    print(json.dumps({"output": str(args.output), "verdicts": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
