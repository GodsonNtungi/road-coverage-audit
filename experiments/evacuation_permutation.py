"""Is the tribal / rural gap in hidden ways out bigger than label shuffling gives?

Labels are shuffled within each region, and separately within each county (tribal and non-tribal
tracts of the same county compared), so a region- or county-wide difference cannot produce the gap.

    uv run python experiments/evacuation_permutation.py
"""
import numpy as np
import pandas as pd

from evacuation_report import load

DRAWS = 5000
rng = np.random.default_rng(20260924)


def gap(y, flag):
    return y[flag].mean() - y[~flag].mean()


def shuffled(flag, groups):
    out = flag.copy()
    for idx in groups:
        out[idx] = rng.permutation(flag[idx])
    return out


def test(e, flag_col, value_col, block):
    ok = e[[flag_col, value_col, block]].dropna()
    y, flag = ok[value_col].to_numpy(), ok[flag_col].astype(bool).to_numpy()
    groups = [np.flatnonzero(ok[block].to_numpy() == b) for b in ok[block].unique()]
    observed = gap(y, flag)
    null = np.array([gap(y, shuffled(flag, groups)) for _ in range(DRAWS)])
    p = (1 + (null >= observed).sum()) / (DRAWS + 1)
    return observed, np.percentile(null, 97.5), p


if __name__ == "__main__":
    e = load()
    e["county"] = e.GEOID.str[:5]
    e["rural"] = e.ur_class.eq("Rural")
    for flag in ["tribal_any", "rural"]:
        for value in ["missing_exits_overture", "missing_exits_overture_track"]:
            for block in ["region", "county"]:
                obs, hi, p = test(e, flag, value, block)
                print(f"{flag:10s} {value:30s} shuffled within {block:6s}: gap {obs:+.3f}  "
                      f"(97.5% of shuffles below {hi:+.3f})  p = {p:.4f}")
