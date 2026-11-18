"""Replay failure probes and preserve trace/ledger evidence without editing Lab 08.

python -m lab9.evidence --out reports/failure_evidence.json
These are explicit bug-switch probes, not additional baseline trials.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from lab8.shapes import SHAPES
from lab9.eval import load_spec, load_world, make_task
from lab9.graders import GRADERS
from lab9.variant_agent import make_shape

PROBES = [
    ("FM-01", "leaky_trace", "C-010", 11),
    ("FM-02", "ignore_denied", "C-007", 11),
    ("FM-03", "ticket_trust", "C-002", 11),
    ("FM-04", "sum_parts", "C-014", 11),
    ("FM-05", "pre_deducted", "C-014", 11),
    ("FM-06", "stale_clause", "C-006", 11),
    ("FM-07", "sibling_refund", "C-001", 11),
    ("FM-08", "misreport", "C-008", 11),
    # No cross-principal bug switch exists: this is a successful negative-control trace.
    ("FM-09", None, "C-113", 11),
]


def collect() -> list[dict]:
    spec = load_spec(Path("config/metric_spec_v2.yaml"))
    world, claims = load_world(spec)
    labels = {c["claim_id"]: c["expected"] for c in claims}
    out = []
    with tempfile.TemporaryDirectory(prefix="lab9-evidence-") as tmp:
        for fm, bug, cid, seed in PROBES:
            name = "evidence_" + (bug or "scope_control")
            SHAPES[name] = make_shape(name, {"no_override", *([bug] if bug else [])})
            trial = make_task(name, world, claims, labels, Path(tmp))({"claim_id": cid, "seed": seed})
            scores = {}
            for mid, grader in GRADERS.items():
                res = grader().evaluate(SimpleNamespace(output=trial, expected_output=labels[cid]))
                scores[mid] = {"value": res.value, "reason": res.reason}
            # blob is redundant; it contains only PUBLIC synthetic canaries in these probes.
            trial.pop("blob")
            out.append({"failure_mode": fm, "probe": bug or "scope_control", "claim_id": cid,
                        "seed": seed, "label": labels[cid], "trial": trial, "graders": scores,
                        "evidence_type": "injected_failure" if bug else "negative_control"})
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/failure_evidence.json")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    evidence = collect()
    out.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    for case in evidence:
        t = case["trial"]
        print(f"{case['failure_mode']} {case['probe']} {case['claim_id']}@{case['seed']}: "
              f"lab8={t['lab8_pass']} ({t['lab8_reason']}); ledger={t['snapshot']['refund_vnd']}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
