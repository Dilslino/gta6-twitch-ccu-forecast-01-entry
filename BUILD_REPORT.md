# BUILD REPORT — gta6-twitch-ccu-forecast-01

- Bounty: gta6-twitch-ccu-forecast-01 ("Forecast GTA VI's launch-day Twitch viewers hour by hour"), $250, FREE, top 1 $50. Entries close 08:00 WIB 19 Nov 2026 (deadline 2026-11-19T01:00:00Z).
- Repo: https://github.com/Dilslino/gta6-twitch-ccu-forecast-01-entry
- Commit: `fa45cbceb17809a3c0a66317072aa46ebdb702d9` (code commit; HEAD adds the commit SHA to this report)
- Anchor: `makefun anchor b9486093d55f1e9385af3c400800306a742e3f4c round 34033510` (drand quicknet, wallet 8cBTj29b2Uwn8yHrhRsss2YkWb5pNV2xJLxaM354zr6x)
- Bundle-transcript bounty (sealedWindow null — no strict recording used).
- Built: 17 Nov 2026, fresh session (attempt 2). main.py written fresh in this session from the verified design of attempt 1; validated with a fresh in-session scorer.

## Design

Pre-5h-anchored kNN (see main.py docstring for the full description):
- Level anchor = mean viewers of the 5 prime-time hours before day_start (19:00-23:00 UTC of the previous day), NOT the noisy dead-hour 00:00 UTC hour-1 print.
- Neighbour features: log(p1) and d = log(p1 / anchor); standardised Euclidean distance; k = 8.
- Curve: per-hour median of neighbours' log(viewers_h / anchor); spread sigma = IQR / 1.349, floored at 0.08 (the floor never binds on practice — smallest practice sigma is 0.157 — it is insurance against the neighbours agreeing almost exactly on the final case, e.g. for a record-breaking launch).
- Forecast: anchor * exp(median + z_tau * sigma), z = (-1.645, -0.674, 0, 0.674, 1.645).
- Fallback chain: full kNN -> house persistence baseline (flat hour-1, spread 0.15*sqrt(h-1)) -> flat hour-1 print. Never crashes, never emits an invalid case.
- Deterministic: no randomness, no wall clock, every ordering explicit (neighbours sorted by distance, name tiebreak).

## Practice results (mean pinball loss, log scale; fresh scorer, grader-style: one case per run, PYTHONHASHSEED=0)

| case | launch | p1 | this forecaster | house baseline | coverage90 | typical miss |
| --- | --- | --- | --- | --- | --- | --- |
| p00 | Marvel's Wolverine | 23,357 | 0.2354 | 0.7437 | 0.83 | 45.6% |
| p01 | Red Dead Redemption 2 | 116,550 | 0.1694 | 0.2868 | 0.96 | 32.0% |
| p02 | God of War Ragnarok | 269,517 | 0.1242 | 0.2146 | 0.96 | 19.2% |
| p03 | Marvel's Spider-Man 2 | 119,087 | 0.1962 | 0.3033 | 0.83 | 31.4% |
| **mean** | | | **0.1813** | **0.3871** | **~0.90** | |

- Beats the house baseline on EVERY practice case (mean 0.1813 vs 0.3871, a 53% reduction).
- Target from the design (<= 0.1818): met.

## Sensitivity checks done before finalising (scratch, not in the entry)

- Sigma multiplier 1.15 / 1.30: mean 0.1850 / 0.1906 — worse; keep 1.0 (IQR/1.349).
- Distance-weighted median: mean 0.1871 — worse; keep the unweighted median.
- Sigma floor 0.05 / 0.08 / 0.10: identical practice mean 0.1813 (floor never binds; min practice sigma 0.157). Floor set to 0.08 as final-case insurance.
- k sweep (from attempt 1): k=4 0.2524, k=6 0.1944, k=8 0.1825/0.1813, k=10 0.1907, k=12 0.1899, k=15 0.1992 — k=8 is the sweet spot.

## Local gates (from RULES.txt) — all pass

- Determinism: 2 runs per case byte-identical (out1 == out2 for all 4 cases).
- No-env-var run: exits 0 with no MAKEFUN_INPUT_DIR / MAKEFUN_OUTPUT_DIR set.
- Runtime: 0.08-0.09 s per case (limit 8 s).
- Output size: 1,457-1,551 bytes per case (limit 65,536).
- Output shape: exactly 23 rows, hours 2-24, 5 quantiles each, all q in (0, 1e9], non-decreasing.
- Score gate: mean 0.1813 < house baseline 0.3871, and beats baseline on every case.
- CLI check (`makefun check`): to be run by the parent after bundling (needs the bundle + submitted commit).
- stdlib-only, no network, no randomness (main.py imports json, math, os, sys, datetime, pathlib only).

## Caveat (final case)

GTA VI will likely be far bigger than any comparable (p1 possibly > 1M). The kNN extrapolates from the biggest launches (ELDEN RING, Cyberpunk 2077, Diablo IV) — untested by practice. The anchor-relative design keeps the extrapolation sane: the median curve of the biggest neighbours already encodes the ~1x peak ratio of huge launches (corr(log p1, log-ratio h21) = -0.936), and the sigma floor guards against a collapsed band.

## Files

- main.py — the entrypoint (self-contained, stdlib-only).
- README.md — design + practice results + badges.
- LICENSE — MIT, SPDX line first (written by `makefun init`).
- .makefun/freshness.json — drand anchor (round 34033510).
