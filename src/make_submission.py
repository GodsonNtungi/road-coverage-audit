"""Join the per-region scores into one two-column submission.

    uv run python src/make_submission.py raw [both|first] [duckroads|albers]  # full precision; picks the scores_<edge>_<roads>.csv
    uv run python src/make_submission.py round6   # components rounded to 6 dp, then the mean rounded
    uv run python src/make_submission.py round5   # final score rounded to 5 dp
    uv run python src/make_submission.py round6dec  # like round6 but exact decimal arithmetic
    uv run python src/make_submission.py round6sub|round6subfac|round6subbiz  # place sub-scores (all / facilities / business) rounded first
"""
import sys
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import pandas as pd

REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]
COMPONENTS = ["transport_gap", "building_gap", "poi_gap"]


def build(mode, edge="both", roads="duckroads"):
    s = pd.concat([pd.read_csv(f"data/cache/{r}/scores_{edge}_{roads}.csv", dtype={"GEOID": str}) for r in REGIONS])
    if mode == "round6":
        s["coverage_gap_score"] = s[COMPONENTS].round(6).mean(axis=1).round(6)
    if mode.startswith("round6sub"):  # place sub-scores rounded to 6 dp before they are averaged
        which = {"round6sub": "fire ems schools cbp", "round6subfac": "fire ems schools", "round6subbiz": "cbp"}[mode]
        subs = s[[f"poi_gap_{k}" for k in ("fire", "ems", "schools", "cbp")]].copy()
        for k in which.split():
            subs[f"poi_gap_{k}"] = subs[f"poi_gap_{k}"].round(6)
        hifld = subs[["poi_gap_fire", "poi_gap_ems", "poi_gap_schools"]].mean(axis=1)
        s["poi_gap"] = pd.concat([hifld, subs.poi_gap_cbp], axis=1).mean(axis=1)
        s["coverage_gap_score"] = s[COMPONENTS].round(6).mean(axis=1).round(6)
    if mode == "round6dec":  # exact decimal mean of the 6 dp components, ties to even
        s["coverage_gap_score"] = s[COMPONENTS].round(6).apply(
            lambda r: float((sum(Decimal(str(v)) for v in r.dropna()) / r.notna().sum())
                            .quantize(Decimal("1e-6"), ROUND_HALF_EVEN)), axis=1)
    if mode == "round5":
        s["coverage_gap_score"] = s.coverage_gap_score.round(5)
    ids = pd.read_csv("data/SampleSubmission.csv", dtype={"GEOID": str}).GEOID
    assert len(s) == len(ids) == s.GEOID.nunique() and set(s.GEOID) == set(ids)
    assert s.coverage_gap_score.between(0, 1).all()
    # the scorer reads the second column, so nothing else goes in the file
    out = Path("submissions") / f"sub_{mode}_{edge}_{roads}.csv"
    out.parent.mkdir(exist_ok=True)
    s[["GEOID", "coverage_gap_score"]].to_csv(out, index=False, float_format="%.10g")
    print(out, len(s), "rows, mean", round(s.coverage_gap_score.mean(), 6))


if __name__ == "__main__":
    build(*sys.argv[1:])
