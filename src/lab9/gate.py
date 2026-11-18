"""Fail-closed release gate: complete paired evidence, slices, safety and ratcheted policy."""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from numbers import Real
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import evalset, stats
from lab9.eval import SPEC, load_spec, per_item


def _finite(value) -> bool:
    return isinstance(value, Real) and math.isfinite(value)


def _derived(mid: str) -> bool:
    return mid in {"pass_5", "cost_per_success"} or bool(re.fullmatch(r"pass_(?:at|hat)_\d+", mid))


def _policy_problems(spec: dict) -> list[str]:
    """Validate policy types before comparisons; malformed policy is not permission."""
    if not isinstance(spec, dict) or not isinstance(spec.get("metrics"), list) or not spec["metrics"]:
        return ["spec requires nonempty metric definitions"]
    if any(not isinstance(m, dict) or not isinstance(m.get("id"), str) or not m["id"] for m in spec["metrics"]):
        return ["invalid metric identity"]
    ids = [m["id"] for m in spec["metrics"]]
    errors = ["duplicate metric definition"] if len(set(ids)) != len(ids) else []
    slices = spec.get("slices", [])
    if not isinstance(slices, list) or any(not isinstance(s, dict) or not isinstance(s.get("name"), str)
                                         or not s["name"] or s.get("metric") not in ids for s in slices):
        return errors + ["invalid slice definitions"]
    if len({(s["name"], s["metric"]) for s in slices}) != len(slices):
        errors.append("duplicate slice definition")
    for definition in [*spec["metrics"], *slices]:
        threshold = definition.get("threshold", {}) if "id" in definition else definition
        if not isinstance(threshold, dict):
            errors.append("threshold must be an object")
            continue
        for key in ("min", "max", "max_increase"):
            if key in threshold and (isinstance(threshold[key], bool) or not _finite(threshold[key])):
                errors.append(f"invalid threshold {key}")
        for container, key in ((threshold, "no_significant_drop"), (definition, "blocking")):
            if key in container and type(container[key]) is not bool:
                errors.append(f"invalid boolean policy {key}")
        if definition.get("kind") == "safety" and threshold.get("max") != 0:
            errors.append("safety must have max=0")
        if "grader" in definition and not isinstance(definition["grader"], str):
            errors.append("invalid grader identity")
    seeds = spec.get("seeds")
    if seeds is not None and (not isinstance(seeds, list) or not seeds or any(type(s) is not int for s in seeds)
                              or len(set(seeds)) != len(seeds)):
        errors.append("invalid policy seed plan")
    bs = spec.get("bootstrap", {})
    if not isinstance(bs, dict):
        errors.append("invalid bootstrap policy")
    elif (bs.get("method", "percentile") != "percentile" or type(bs.get("rng", 2027)) is not int
          or type(bs.get("n_resamples", 1000)) is not int or bs.get("n_resamples", 1000) <= 0
          or not _finite(bs.get("confidence", .95)) or not 0 < bs.get("confidence", .95) < 1):
        errors.append("invalid paired percentile bootstrap policy")
    return errors


def _ratchet(spec: dict, base_spec: dict) -> list[str]:
    """Existing requirements survive policy edits; a new version requires a new baseline."""
    problems = []
    for group, key in (("metrics", lambda x: x.get("id")),
                       ("slices", lambda x: (x.get("name"), x.get("metric")))):
        current = {key(m): m for m in spec.get(group, [])}
        for old in base_spec.get(group, []):
            identity = key(old)
            if identity not in current:
                problems.append(f"ratchet: removed {group} {identity}")
                continue
            new = current[identity]
            old_th = old.get("threshold", {}) if group == "metrics" else old
            new_th = new.get("threshold", {}) if group == "metrics" else new
            for name, value in old_th.items():
                if name in {"min", "max", "max_increase"}:
                    candidate = new_th.get(name)
                    if not _finite(candidate) or (candidate < value if name == "min" else candidate > value):
                        problems.append(f"ratchet: loosened {identity}/{name}")
                elif name == "no_significant_drop" and value and not new_th.get(name):
                    problems.append(f"ratchet: removed no_significant_drop for {identity}")
                elif group == "metrics" and name not in {"min", "max", "max_increase", "no_significant_drop"}:
                    if new_th.get(name) != value:
                        problems.append(f"ratchet: changed threshold semantics {identity}/{name}")
            if old.get("blocking") and not new.get("blocking"):
                problems.append(f"ratchet: disabled blocking {identity}")
            for name in ("kind", "grader", "level"):
                if name in old and new.get(name) != old[name]:
                    problems.append(f"ratchet: changed evaluator semantics {identity}/{name}")
    if base_spec.get("seeds") is not None and set(spec.get("seeds", [])) != set(base_spec["seeds"]):
        problems.append("ratchet: changed seed plan without a new baseline")
    old_bs, new_bs = base_spec.get("bootstrap", {}), spec.get("bootstrap", {})
    for name in ("method", "rng"):
        if name in old_bs and new_bs.get(name) != old_bs[name]:
            problems.append(f"ratchet: changed bootstrap {name}")
    if new_bs.get("confidence", .95) > old_bs.get("confidence", .95):
        problems.append("ratchet: wider confidence can hide a significant drop")
    if new_bs.get("n_resamples", 1000) < old_bs.get("n_resamples", 1000):
        problems.append("ratchet: reduced bootstrap resamples")
    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """Validate both reports, the complete Cartesian trial plan, aggregates and policy.

    Baseline evidence is checked as strictly as PR evidence. No intersection-only pairing,
    missing-value filtering, seed substitution, or relabelled slice can make a run green.
    """
    if not isinstance(pr, dict) or not isinstance(base, dict):
        return ["PR and baseline reports must be objects"]
    problems = _policy_problems(spec)
    if problems:
        return problems
    metrics = spec["metrics"]
    ids = [m["id"] for m in metrics]
    if base_spec is None:
        manifest = base.get("manifest")
        base_spec = manifest.get("metric_spec") if isinstance(manifest, dict) else None
    if base_spec is not None:
        invalid = _policy_problems(base_spec)
        if invalid:
            return [f"baseline policy: {p}" for p in invalid]
        # check() compares identical eval_set_sha only: changing a version string cannot
        # exempt the exact same evidence from an existing release requirement.
        problems.extend(_ratchet(spec, base_spec))
    expected_items = None
    if spec.get("eval_set"):
        path = Path(spec["eval_set"])
        if not path.is_file():
            problems.append("spec eval_set is missing")
        else:
            items = evalset.load_jsonl(path)
            expected_items = {i["item_id"]: i for i in items}
            if len(items) != len(expected_items):
                problems.append("duplicate item in eval set")
    plans, tags = {}, {}
    row_ids = [mid for mid in ids if not _derived(mid)]
    for title, report in (("PR", pr), ("baseline", base)):
        if not isinstance(report, dict):
            problems.append(f"{title}: report is not an object")
            continue
        manifest, rows, values = report.get("manifest"), report.get("rows"), report.get("metrics")
        if not isinstance(manifest, dict) or not isinstance(rows, list) or not isinstance(values, dict):
            problems.append(f"{title}: missing manifest, rows or metrics")
            continue
        start = len(problems)
        if "evaluator_failures" not in report or report["evaluator_failures"] != []:
            problems.append(f"{title}: evaluator_failures must be an empty list")
        for mid, value in values.items():
            if not _finite(value):
                problems.append(f"{title}: metric {mid} is missing/nonfinite")
        for mid in ids:
            if mid not in values:
                problems.append(f"{title}: missing metric {mid}")
        count, seeds = manifest.get("items"), manifest.get("seeds")
        if type(count) is not int or count <= 0 or not isinstance(seeds, list) or not seeds or any(type(s) is not int for s in seeds):
            problems.append(f"{title}: invalid manifest item/seed plan")
            continue
        if len(set(seeds)) != len(seeds):
            problems.append(f"{title}: duplicate manifest seeds")
        if spec.get("seeds") is not None and set(seeds) != set(spec["seeds"]):
            problems.append(f"{title}: manifest seeds differ from spec")
        if not manifest.get("eval_set_sha"):
            problems.append(f"{title}: missing eval_set_sha")
        if "labels_sha" in manifest and spec.get("labels"):
            labels = Path(spec["labels"])
            if not labels.is_file() or manifest["labels_sha"] != evalset.sha12(labels):
                problems.append(f"{title}: labels SHA differs from evaluation labels")
        if expected_items is not None:
            if count != len(expected_items) or manifest.get("eval_set_sha") != evalset.sha12(Path(spec["eval_set"])):
                problems.append(f"{title}: manifest differs from source eval set")
            if manifest.get("eval_set_version", spec.get("eval_set_version")) != spec.get("eval_set_version"):
                problems.append(f"{title}: eval set version differs from spec")
        if len(rows) != count * len(seeds):
            problems.append(f"{title}: row count differs from manifest")
        pairs, item_tags = [], {}
        for r in rows:
            if not isinstance(r, dict) or not isinstance(r.get("item_id"), str) or type(r.get("seed")) is not int:
                problems.append(f"{title}: invalid row identity")
                continue
            iid, seed = r["item_id"], r["seed"]
            pairs.append((iid, seed))
            slice_tags = r.get("slices", [])
            if not isinstance(slice_tags, list) or any(not isinstance(t, str) for t in slice_tags) or len(set(slice_tags)) != len(slice_tags):
                problems.append(f"{title}: invalid slice tags for {iid}")
            else:
                current = frozenset(slice_tags)
                if iid in item_tags and item_tags[iid] != current:
                    problems.append(f"{title}: inconsistent slice tags within {iid}")
                item_tags[iid] = current
                if expected_items is not None and (iid not in expected_items or current != frozenset(expected_items[iid].get("slices", []))):
                    problems.append(f"{title}: slice/item differs from eval set for {iid}")
            for mid in row_ids:
                if not _finite(r.get(mid)):
                    problems.append(f"{title}: {iid}@{seed} missing/nonfinite grader {mid}")
            if "cost_per_success" in ids and (not _finite(r.get("cost")) or r["cost"] < 0):
                problems.append(f"{title}: missing/invalid row cost")
        pair_counts = Counter(pairs)
        if any(n != 1 for n in pair_counts.values()):
            problems.append(f"{title}: duplicate item/seed row")
        item_ids = {i for i, _ in pairs}
        if len(item_ids) != count or set(pairs) != {(i, s) for i in item_ids for s in seeds}:
            problems.append(f"{title}: incomplete Cartesian item/seed plan")
        if expected_items is not None and item_ids != set(expected_items):
            problems.append(f"{title}: item IDs differ from source eval set")
        plans[title], tags[title] = set(pairs), item_tags
        if len(problems) != start:
            continue
        # Recompute, so tampering with only the headline metrics cannot hide bad rows.
        for m in metrics:
            mid = m["id"]
            if mid in row_ids:
                vals = [r[mid] for r in rows]
                want = sum(vals) if m.get("kind") == "safety" else round(sum(vals) / len(vals), 4)
                if not math.isclose(values[mid], want, abs_tol=5e-5, rel_tol=1e-9):
                    problems.append(f"{title}: aggregate disagrees with rows for {mid}")
                if m.get("kind") == "safety" and any(v < 0 or int(v) != v for v in vals):
                    problems.append(f"{title}: invalid negative/noninteger safety violation count")
        derived = [mid for mid in ids if _derived(mid)]
        if derived:
            if any(not _finite(r.get("pass_rate")) or r["pass_rate"] not in (0, 1) for r in rows):
                problems.append(f"{title}: derived metric needs binary pass_rate rows")
                continue
            for mid in derived:
                try:
                    if mid == "cost_per_success":
                        passes = sum(r["pass_rate"] for r in rows)
                        want = round(sum(r["cost"] for r in rows) / passes, 4) if passes else None
                    else:
                        estimates = per_item(report, mid)
                        want = round(sum(estimates.values()) / len(estimates), 4)
                except ValueError as exc:
                    problems.append(f"{title}: invalid derived metric {mid}: {exc}")
                    continue
                if not _finite(want) or not math.isclose(values[mid], want, abs_tol=5e-5, rel_tol=1e-9):
                    problems.append(f"{title}: derived aggregate disagrees with rows for {mid}")
    if plans.get("PR") != plans.get("baseline"):
        problems.append("PR item/seed pairs differ from baseline")
    if tags.get("PR") != tags.get("baseline"):
        problems.append("PR slice membership differs from baseline")
    return problems


def _paired(pr: dict, base: dict, mid: str, bs: dict, slice_name: str | None = None):
    a, b = per_item(pr, mid, slice_name), per_item(base, mid, slice_name)
    if not a or a.keys() != b.keys():
        raise ValueError("missing or unpaired item evidence")
    keys = sorted(a)
    return stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                  n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027),
                                  confidence=bs.get("confidence", .95))


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """Check every configured slice on paired item means; absent evidence blocks closed."""
    blocked, lines = [], []
    for s in spec.get("slices", []):
        name, mid = s["name"], s["metric"]
        sid = f"slice:{name}/{mid}"
        a, b = per_item(pr, mid, name), per_item(base, mid, name)
        verdict, note, value = True, "", None
        pr_counts = Counter(r["item_id"] for r in pr["rows"] if name in r.get("slices", []))
        base_counts = Counter(r["item_id"] for r in base["rows"] if name in r.get("slices", []))
        field = "pass_rate" if _derived(mid) and mid != "cost_per_success" else mid
        complete = (all(v == len(pr["manifest"]["seeds"]) for v in pr_counts.values())
                    and all(v == len(base["manifest"]["seeds"]) for v in base_counts.values())
                    and all(_finite(r.get(field)) for rep in (pr, base) for r in rep["rows"]
                            if name in r.get("slices", [])))
        if not a or a.keys() != b.keys() or not complete:
            verdict, note = False, "MISSING/UNPAIRED slice evidence"
        else:
            safety = any(m["id"] == mid and m.get("kind") == "safety" for m in spec["metrics"])
            value = sum(float(r[mid]) for r in pr["rows"] if name in r.get("slices", [])) if safety else sum(a.values()) / len(a)
            if "min" in s and value < s["min"] or "max" in s and value > s["max"]:
                verdict = False
            if s.get("no_significant_drop"):
                try:
                    d, lo, hi = _paired(pr, base, mid, spec.get("bootstrap", {}), name)
                    note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                    if hi < 0:
                        verdict = False
                except ValueError as exc:
                    verdict, note = False, f"INTEGRITY {exc}"
        if not verdict and (s.get("blocking") or value is None):
            blocked.append(sid)
        lines.append(f"  {sid:<36} {value!s:<8} {note:<36} {'ok' if verdict else 'BLOCK' if sid in blocked else 'warn'}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from baseline: re-run on the same eval set"]
    blocked, lines = [], []
    for m in spec["metrics"]:
        mid, th, value = m["id"], m.get("threshold", {}), pr["metrics"][m["id"]]
        verdict, note = True, ""
        if "max" in th and value > th["max"] or "min" in th and value < th["min"]:
            verdict = False
        if "max_increase" in th and value > base["metrics"][mid] * (1 + th["max_increase"]):
            verdict = False
        if th.get("no_significant_drop"):
            try:
                d, lo, hi = _paired(pr, base, mid, spec.get("bootstrap", {}))
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = False
            except ValueError as exc:
                return ["integrity"], [f"  INTEGRITY {mid}: {exc}"]
        if not verdict and m.get("blocking"):
            blocked.append(mid)
        label = "ok" if verdict else "BLOCK" if m.get("blocking") else "warn"
        lines.append(f"  {mid:<24} {value!s:<8} {json.dumps(th):<46} {note:<28} {label}")
    sb, sl = slice_check(pr, base, spec)
    return blocked + sb, lines + sl


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="trusted base revision's metric spec for ratchet")
    args = ap.parse_args(argv)
    try:
        pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
        blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"  INTEGRITY invalid report/spec: {exc}")
        print("exit 1 — blocked: integrity")
        return 1
    print(f"gate: PR {pr.get('run_id', '?')} vs main {base.get('run_id', '?')} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    print(f"exit 1 — blocked: {', '.join(blocked)}" if blocked else "exit 0 — merge")
    return int(bool(blocked))


if __name__ == "__main__":
    raise SystemExit(main())
