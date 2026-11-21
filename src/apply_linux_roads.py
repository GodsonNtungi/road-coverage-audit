"""Swap the road gap for the one computed from linux/arm64 road lengths (src/roads_linux.py).

Reads scores_both_duckroads_centroid.csv, writes scores_both_linuxroads_centroid.csv per region.

    uv run python src/apply_linux_roads.py
"""
import pandas as pd

from score import gap

REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]

for r in REGIONS:
    d = f"data/cache/{r}"
    s = pd.read_csv(f"{d}/scores_both_duckroads_centroid.csv", dtype={"GEOID": str}).set_index("GEOID")
    ov = pd.read_csv(f"{d}/ov_len_linux.csv", dtype={"GEOID": str}).set_index("GEOID").ov_len
    tg = pd.read_csv(f"{d}/tg_len_linux.csv", dtype={"GEOID": str}).set_index("GEOID").tg_len
    new = gap(ov.reindex(s.index, fill_value=0), tg.reindex(s.index, fill_value=0))
    changed = (pd.Series(new, s.index).fillna(-1) - s.transport_gap.fillna(-1)).abs() > 1e-12
    s["transport_gap"] = new
    s["coverage_gap_score"] = s[["transport_gap", "building_gap", "poi_gap"]].mean(axis=1)
    s.reset_index().to_csv(f"{d}/scores_both_linuxroads_centroid.csv", index=False)
    print(f"{r}: road gap changed in {int(changed.sum())} tracts {list(s.index[changed][:8])}")
