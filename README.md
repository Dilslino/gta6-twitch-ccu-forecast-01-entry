[![make.fun](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Dilslino/gta6-twitch-ccu-forecast-01-entry/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Dilslino/gta6-twitch-ccu-forecast-01-entry/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01)

# GTA VI launch-day Twitch viewers, hour by hour

Entry for the [make.fun bounty gta6-twitch-ccu-forecast-01](https://make.fun/bounty/gta6-twitch-ccu-forecast-01):
forecast the release day's hourly Twitch viewers (hours 2-24) as five
quantiles (5/25/50/75/95%) on the log scale, scored by mean pinball loss.
The program reads every `<id>.in` in the input directory (env
`MAKEFUN_INPUT_DIR`, else `/input`) and writes `<id>.out` to the output
directory (env `MAKEFUN_OUTPUT_DIR`, else `/output`).

## Design: pre-5h-anchored kNN

The hour-1 print (00:00 UTC, a dead hour) is a noisy, depressed read of a
launch's size, so the level is anchored to the mean viewers of the five
prime-time hours right before the release day (19:00-23:00 UTC of the day
before). Each comparable launch is summarised by two features: log(p1),
the log of its hour-1 print, and d = log(p1 / anchor), how depressed its
hour 1 was against its own pre-day prime-time level. The target's eight
nearest neighbours in that (standardised) 2-D space lend their release-day
curves: for each hour h the median of the neighbours' log(viewers_h /
anchor) is the median log-ratio, and the IQR of those log-ratios (as a
normal sigma, IQR / 1.349, floored at 0.08) is the spread. The forecast is
anchor * exp(median + z_tau * sigma).

Launch size drives the evening peak almost entirely (corr(log p1,
log-ratio at hour 21) about -0.94 across the comparables): small launches
peak ~9x their hour 1, huge ones ~1x, and the neighbours carry that shape.

Fallbacks (never crash, never emit an invalid case): if the anchor cannot
be read, or fewer than four usable comparables exist, fall back to the
house persistence baseline (flat hour-1 print, spread 0.15 * sqrt(h - 1));
if even that is impossible, emit a flat hour-1 print.

## Practice results (mean pinball loss on the log scale)

| case | launch | this forecaster | house baseline |
| --- | --- | --- | --- |
| p00 | Marvel's Wolverine (p1 23,357) | 0.2354 | 0.7437 |
| p01 | Red Dead Redemption 2 (p1 116,550) | 0.1694 | 0.2868 |
| p02 | God of War Ragnarok (p1 269,517) | 0.1242 | 0.2146 |
| p03 | Marvel's Spider-Man 2 (p1 119,087) | 0.1962 | 0.3033 |
| **mean** | | **0.1813** | **0.3871** |

Beats the house baseline on every practice case. 90% coverage 0.83 /
0.96 / 0.96 / 0.83. Deterministic (two runs byte-identical), ~0.08 s per
case, ~1.5 KB output per case.

## Run

```sh
python3 main.py   # reads $MAKEFUN_INPUT_DIR/*.in, writes $MAKEFUN_OUTPUT_DIR/*.out
```

Python 3.13, standard library only, no network, no randomness.

## License

MIT — see `LICENSE`.
