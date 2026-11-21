"""Share of each tract's real ways out (Census TIGER) that Overture's road layers do not show.

    uv run python experiments/evacuation_report.py
"""
import numpy as np
import pandas as pd

REGIONS = ["northern-ca", "maricopa-az", "eastern-ok", "south-central-tx"]
VARIANTS = {"exits_overture": "drivable classes (the challenge's escape-route layer)",
            "exits_overture_track": "+ unpaved 'track' roads",
            "exits_overture_all": "+ track and service roads"}


def load(band=30):
    rows = []
    for r in REGIONS:
        e = pd.read_csv(f"data/cache/{r}/" + ("exits.csv" if band == 30 else f"exits_b{band}.csv"), dtype={"GEOID": str})
        s = pd.read_parquet(f"data/strata/{r}/{r}-strata-tract-table.parquet",
                            columns=["GEOID", "usfs_WHP_mean", "ur_class", "tribal_any", "aiannh_name",
                                     "svi_overall", "pop_total"])
        e = e.merge(s, on="GEOID")
        # quartiles within each region: wildfire hazard scales differ a lot between regions
        e["wildfire"] = pd.qcut(e.usfs_WHP_mean.rank(method="first"), 4, labels=["low", "mid-low", "mid-high", "high"])
        rows.append(e)
    e = pd.concat(rows)
    e = e[e.exits_tiger > 0].copy()
    for v in VARIANTS:
        e[f"missing_{v}"] = (e.exits_tiger - e[v]).clip(lower=0) / e.exits_tiger
    e["svi_high"] = e.svi_overall >= 0.75
    return e


def table(e, by):
    cols = [f"missing_{v}" for v in VARIANTS]
    t = e.groupby(by, observed=True)[cols].mean()
    t.insert(0, "tracts", e.groupby(by, observed=True).size())
    t.columns = ["tracts"] + list(VARIANTS.values())
    return t


if __name__ == "__main__":
    e = load()
    e.to_csv("experiments/exits_all.csv", index=False)
    pd.set_option("display.width", 200)
    for by in [["wildfire"], ["region", "wildfire"], ["ur_class", "wildfire"], ["tribal_any"], ["region", "tribal_any"],
               ["svi_high"]]:
        print(f"\n== share of real ways out not shown, by {' x '.join(by)}")
        print(table(e, by).round(3).to_string())
    worst = e[(e.wildfire == "high") & (e.exits_tiger >= 5)].sort_values("missing_exits_overture", ascending=False)
    print("\n== high-wildfire tracts losing the most ways out in the escape-route layer")
    print(worst[["GEOID", "region", "exits_tiger", "exits_overture", "exits_overture_track", "pop_total",
                 "ur_class", "aiannh_name"]].head(15).to_string(index=False))
    hi = e[e.wildfire == "high"]
    lost = hi.exits_tiger - hi.exits_overture
    print(f"\nhigh-wildfire tracts: {len(hi):,}, people {int(hi.pop_total.sum()):,}; "
          f"ways out hidden from the escape-route layer {int(lost.clip(lower=0).sum()):,} "
          f"of {int(hi.exits_tiger.sum()):,}")
