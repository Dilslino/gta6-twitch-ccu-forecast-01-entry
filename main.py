"""gta6-twitch-ccu-forecast-01 entry: pre-5h-anchored kNN forecaster (Python 3.13, stdlib only).

Design
------
Forecast the release day's hourly Twitch viewers (hours 2..24) as five
quantiles (5/25/50/75/95%) on the log scale, from the case's hour-1 print
and the comparables the case ships.

The hour-1 print (00:00 UTC, a dead hour) is a noisy, depressed read of a
launch's size, so the level is anchored not to it but to the mean viewers of
the five prime-time hours right before the release day (19:00-23:00 UTC of
the day before). Each comparable launch is summarised by two features:
log(p1), the log of its hour-1 print, and d = log(p1 / anchor), how
depressed its hour 1 was against its own pre-day prime-time level. The
target's eight nearest neighbours in that (standardised) 2-D space lend
their release-day curves: for each hour h the median of the neighbours'
log(viewers_h / anchor) is the median log-ratio, and the IQR of those
log-ratios (as a normal sigma, IQR / 1.349, floored at 0.08 - the floor
never binds on practice, where the smallest sigma is 0.157; it is
insurance against the neighbours agreeing almost exactly on the final
case and the 90% band collapsing).
The forecast is anchor * exp(median + z_tau * sigma), z the standard
normal quantiles. Launch size drives the evening peak almost entirely
(corr(log p1, log-ratio at hour 21) about -0.94 across the comparables):
small launches peak ~9x their hour 1, huge ones ~1x, and the neighbours
carry that shape.

Practice (four past launches, mean pinball loss on the log scale):
  house baseline  0.3871 (p00 0.7437, p01 0.2868, p02 0.2146, p03 0.3033)
  this forecaster 0.1813 (p00 0.2354, p01 0.1694, p02 0.1242, p03 0.1962)
beating the baseline on every practice case, with 90% coverage about 0.90.

Fallbacks (never crash, never emit an invalid case): if the anchor cannot
be read, or fewer than four usable comparables exist, fall back to the
house persistence baseline (flat hour-1 print, spread widening as
0.15 * sqrt(h - 1)); if even that is impossible, emit a flat hour-1 print.

The program reads every <id>.in in the input directory (env
MAKEFUN_INPUT_DIR, else /input) in name order and writes <id>.out to the
output directory (env MAKEFUN_OUTPUT_DIR, else /output). Deterministic:
no randomness, no wall clock, every ordering explicit.
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
K_NEIGHBOURS = 8
MIN_COMPARABLES = 4
SIGMA_FLOOR = 0.08  # insurance only: the smallest sigma on any practice
                    # hour is 0.157, so this floor never binds in practice;
                    # it stops the 90% band collapsing to near-zero width
                    # if the nearest neighbours ever agree almost exactly
                    # (a real risk for a record-breaking launch, where the
                    # eight biggest launches are few and their curves can
                    # cluster) - a collapsed band is punished brutally by
                    # the pinball loss when the truth falls outside it.
BASELINE_SIGMA = 0.15


def round2(x):
    """x rounded to 2 decimals, half up (as the starter rounds it)."""
    scaled = x * 100.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100.0
    return int(value) if value.is_integer() else value


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def hourly_map(hourly):
    """{datetime: viewers} for points with a usable positive viewer count."""
    out = {}
    for pt in hourly or []:
        try:
            v = float(pt["viewers"])
        except (KeyError, TypeError, ValueError):
            continue
        if v > 0:
            try:
                out[parse_ts(pt["from"])] = v
            except (KeyError, TypeError, ValueError):
                continue
    return out


def anchor_from_map(m, day_start):
    """Mean viewers of the five prime-time hours before day_start.

    The five hours immediately before midnight (19:00-23:00 UTC of the
    previous day). Uses whatever of them is present, needing at least
    three; None when too few are available.
    """
    vals = []
    for i in (5, 4, 3, 2, 1):
        v = m.get(day_start - timedelta(hours=i))
        if v is not None:
            vals.append(v)
    if len(vals) < 3:
        return None
    return sum(vals) / len(vals)


def comparable_features(comp):
    """(p1, anchor, d, curve) for one comparable launch, or None.

    p1 is its hour-1 print (viewers at its day_start); anchor is its
    pre-day prime-time mean; d = log(p1 / anchor); curve[h] is its
    viewers at hour h of its release day, h = 2..24. A comparable is
    usable only when all of those exist.
    """
    try:
        day_start = parse_ts(comp["day_start"])
    except (KeyError, TypeError, ValueError):
        return None
    m = hourly_map(comp.get("hourly"))
    p1 = m.get(day_start)
    if p1 is None or p1 <= 0:
        return None
    anchor = anchor_from_map(m, day_start)
    if anchor is None or anchor <= 0:
        return None
    curve = {}
    for h in range(2, 25):
        v = m.get(day_start + timedelta(hours=h - 1))
        if v is None or v <= 0:
            return None
        curve[h] = v
    return {"p1": p1, "anchor": anchor, "d": math.log(p1 / anchor),
            "curve": curve, "name": str(comp.get("name", ""))}


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def quantile_sorted(s, q):
    """Linear-interpolation quantile of an already sorted list."""
    if not s:
        return float("nan")
    pos = (len(s) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] * (hi - pos) + s[hi] * (pos - lo)


def knn_rows(case, p1, anchor, hours):
    """The kNN forecast rows for one case, or None when it cannot run."""
    d_target = math.log(p1 / anchor)
    logp1_target = math.log(p1)
    comps = []
    for comp in case.get("comparables") or []:
        fc = comparable_features(comp)
        if fc is not None:
            comps.append(fc)
    if len(comps) < MIN_COMPARABLES:
        return None
    k = min(K_NEIGHBOURS, len(comps))

    # Standardise the two neighbour features by the comparables' spread,
    # so launch size and hour-1 depression weigh comparably.
    xs = [math.log(c["p1"]) for c in comps]
    ds = [c["d"] for c in comps]
    mx = sum(xs) / len(xs)
    md = sum(ds) / len(ds)
    vx = sum((x - mx) ** 2 for x in xs) / len(xs)
    vd = sum((d - md) ** 2 for d in ds) / len(ds)
    sx = math.sqrt(vx) or 1.0
    sd = math.sqrt(vd) or 1.0

    def dist(c):
        return math.hypot((math.log(c["p1"]) - mx) / sx - (logp1_target - mx) / sx,
                          (c["d"] - md) / sd - (d_target - md) / sd)

    # Deterministic order: distance first, name as tiebreak.
    comps.sort(key=lambda c: (dist(c), c["name"]))
    neigh = comps[:k]

    rows = []
    for h in hours:
        logs = [math.log(c["curve"][h] / c["anchor"]) for c in neigh]
        med = median(logs)
        s = sorted(logs)
        iqr = quantile_sorted(s, 0.75) - quantile_sorted(s, 0.25)
        sigma = max(iqr / 1.349, SIGMA_FLOOR)
        q = [anchor * math.exp(med + z * sigma) for z in Z]
        q = [min(max(v, 1.0), 1e9) for v in q]
        q = sorted(q)
        rows.append({"hour": h, "q": [round2(v) for v in q]})
    return rows


def baseline_rows(p1, hours):
    """House persistence baseline: flat hour-1 print, widening spread."""
    p1 = max(1.0, float(p1))
    rows = []
    for h in hours:
        q = [round2(p1 * math.exp(z * BASELINE_SIGMA * math.sqrt(h - 1))) for z in Z]
        rows.append({"hour": h, "q": q})
    return rows


def forecast_case(case):
    """Forecast one case, with the fallback chain to the baseline."""
    hours = [row["hour"] for row in case["forecast"]]
    known = next((r for r in case.get("known") or [] if r.get("hour") == 1), None)
    p1 = max(1.0, float(known["viewers"])) if known is not None else 1.0
    try:
        day_start = parse_ts(case["day_start"])
        hist = hourly_map(case.get("history_hourly"))
        anchor = anchor_from_map(hist, day_start)
    except (KeyError, TypeError, ValueError):
        anchor = None
    rows = None
    if anchor is not None and anchor > 0:
        rows = knn_rows(case, p1, anchor, hours)
    if rows is None:
        rows = baseline_rows(p1, hours)
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        try:
            forecast = forecast_case(case)
        except Exception:
            # Last resort: a flat hour-1 print is always a valid case.
            known = next((r for r in case.get("known") or [] if r.get("hour") == 1), None)
            p1 = max(1.0, float(known["viewers"])) if known is not None else 1.0
            hours = [row["hour"] for row in case["forecast"]]
            forecast = {"hours": [{"hour": h, "q": [round2(p1)] * 5} for h in hours]}
        (OUTPUT_DIR / (path.stem + ".out")).write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
