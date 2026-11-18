"""Validated binary calibration and paired, item-level reliability statistics."""
from __future__ import annotations

import math
from collections.abc import Sequence
from numbers import Integral

import numpy as np
from scipy.stats import bootstrap

POS = "FAIL"


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """Return tp/fp/fn/tn; FAIL is the positive class. Reject missing/invalid labels."""
    if len(human) != len(judge) or not len(human):
        raise ValueError("human and judge must be nonempty and equally sized")
    cm = dict.fromkeys(("tp", "fp", "fn", "tn"), 0)
    for h, j in zip(human, judge):
        if h not in ("PASS", "FAIL") or j not in ("PASS", "FAIL"):
            raise ValueError("labels must be PASS or FAIL")
        cm[("tp" if j == POS else "fn") if h == POS else ("fp" if j == POS else "tn")] += 1
    return cm


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    tp, fp, fn = cm["tp"], cm["fp"], cm["fn"]
    return tp / (tp + fp) if tp + fp else 0.0, tp / (tp + fn) if tp + fn else 0.0


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """Chance-corrected agreement. Undefined agreement must fail calibration."""
    cm = confusion(human, judge)
    tp, fp, fn, tn = (cm[k] for k in ("tp", "fp", "fn", "tn"))
    n = tp + fp + fn + tn
    expected = (tp + fn) * (tp + fp) + (tn + fp) * (tn + fn)
    if expected == n * n:
        raise ValueError("kappa undefined: expected agreement is 1")
    return (n * (tp + tn) - expected) / (n * n - expected)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct prevalence, reject an unidentifiable classifier, clip to [0, 1]."""
    if any(not math.isfinite(x) or not 0 <= x <= 1 for x in (observed_rate, sensitivity, specificity)):
        raise ValueError("rates must be finite probabilities")
    denominator = sensitivity + specificity - 1
    if math.isclose(denominator, 0, abs_tol=1e-12):
        raise ValueError("Rogan-Gladen undefined: sensitivity + specificity = 1")
    return min(1.0, max(0.0, (observed_rate + specificity - 1) / denominator))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """PR minus baseline, same items/order, using scipy paired percentile bootstrap."""
    x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or x.shape != y.shape or not x.size:
        raise ValueError("paired samples must be nonempty equal-length vectors")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("paired samples must be finite")
    if isinstance(n_resamples, bool) or not isinstance(n_resamples, Integral) or n_resamples <= 0:
        raise ValueError("n_resamples must be a positive integer")
    if not math.isfinite(confidence) or not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    if np.array_equal(x, y):
        return 0.0, 0.0, 0.0
    delta = float(np.mean(x) - np.mean(y))
    if len(x) == 1:
        return delta, delta, delta
    res = bootstrap((x, y), lambda u, v, axis: np.mean(u - v, axis=axis), paired=True,
                    method="percentile", n_resamples=n_resamples,
                    confidence_level=confidence, rng=np.random.default_rng(rng))
    return delta, float(res.confidence_interval.low), float(res.confidence_interval.high)


def _validate_k(n: int, c: int, k: int) -> None:
    if any(isinstance(x, bool) or not isinstance(x, Integral) for x in (n, c, k)):
        raise ValueError("n, c, k must be integers")
    if n <= 0 or not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError("require n > 0, 0 <= c <= n, 1 <= k <= n")


def pass_at_k(n: int, c: int, k: int) -> float:
    """1 - C(n-c, k)/C(n, k): at least one success without replacement."""
    _validate_k(n, c, k)
    if n - c < k:
        return 1.0
    # Use the shorter equivalent product, and expm1 to retain tiny probabilities.
    length, removed = (k, c) if k <= c else (c, k)
    return -math.expm1(math.fsum(math.log1p(-removed / (n - i)) for i in range(length)))


def pass_hat_k(n: int, c: int, k: int) -> float:
    """C(c, k)/C(n, k): all k successes without replacement (pass^k)."""
    _validate_k(n, c, k)
    if c < k:
        return 0.0
    length, removed = (k, n - c) if k <= n - c else (n - c, k)
    return math.exp(math.fsum(math.log1p(-removed / (n - i)) for i in range(length)))
