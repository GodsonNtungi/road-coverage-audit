"""Which real bus/rail stops (agency GTFS feeds) are missing from Overture, and whose are they?

A GTFS stop counts as mapped when Overture has a transit stop within MATCH_METRES.

    uv run python experiments/transit_gap.py
"""
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]
GTFS = Path("data/external/gtfs")
MATCH_METRES = 50
ALBERS = "EPSG:5070"


def gtfs_stops():
    out = []
    for z in sorted(GTFS.glob("*.zip")):
        try:
            with zipfile.ZipFile(z) as f:
                s = pd.read_csv(f.open("stops.txt"), dtype=str)
        except (zipfile.BadZipFile, KeyError):
            print("skipping unreadable feed", z.name)
            continue
        # location_type 0/blank = where riders board; stations and entrances are not stops
        s = s[s.get("location_type", pd.Series("0", index=s.index)).fillna("0").isin(["0", ""])]
        s = s.dropna(subset=["stop_lat", "stop_lon"])
        out.append(pd.DataFrame({"feed": z.stem, "stop_id": s.stop_id, "name": s.get("stop_name"),
                                 "lat": s.stop_lat.astype(float), "lon": s.stop_lon.astype(float)}))
    s = pd.concat(out).drop_duplicates(["feed", "stop_id"])
    return gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s.lon, s.lat), crs="OGC:CRS84")


def main():
    tracts = pd.concat([gpd.read_parquet(f"data/cache/{r}/tracts.parquet").assign(region=r) for r in REGIONS])
    tracts = gpd.GeoDataFrame(tracts, crs="OGC:CRS84")
    scored = pd.concat([pd.read_csv(f"data/cache/{r}/sample-submission.csv", dtype=str).GEOID for r in REGIONS])
    tracts = tracts[tracts.GEOID.isin(scored)]

    ov = pd.concat([gpd.read_parquet(f"data/cache/{r}/transit.parquet") for r in REGIONS])
    ov = gpd.GeoDataFrame(ov[ov.subtype == "transit"], crs="OGC:CRS84")
    ov["geometry"] = ov.geometry.representative_point()

    g = gtfs_stops()
    g = gpd.sjoin(g, tracts[["GEOID", "region", "geometry"]], predicate="within").drop(columns="index_right")
    near = gpd.sjoin_nearest(g.to_crs(ALBERS), ov[["geometry"]].to_crs(ALBERS), how="left",
                             max_distance=MATCH_METRES, distance_col="d")
    g["mapped"] = near.groupby(level=0).d.min().reindex(g.index).notna()
    print(f"{len(g):,} real stops in scored tracts from {g.feed.nunique()} feeds; "
          f"{g.mapped.mean():.1%} have an Overture stop within {MATCH_METRES} m")
    print(g.groupby("feed").mapped.agg(["size", "mean"]).round(3).sort_values("size", ascending=False).to_string())

    t = g.groupby("GEOID").agg(real=("mapped", "size"), mapped=("mapped", "sum")).reset_index()
    t["stop_gap"] = 1 - t.mapped / t.real
    strata = pd.concat([pd.read_parquet(f"data/strata/{r}/{r}-strata-tract-table.parquet",
                                        columns=["GEOID", "pop_total", "svi_overall", "svi_housing_transport",
                                                 "svi_minority", "ur_class", "tribal_any"]) for r in REGIONS])
    t = t.merge(strata, on="GEOID").merge(tracts[["GEOID", "region"]], on="GEOID")
    t.to_csv("experiments/transit_gap_tracts.csv", index=False)

    t["housing_transport_q"] = pd.qcut(t.svi_housing_transport, 4, labels=["Q1 least", "Q2", "Q3", "Q4 most"])
    t["svi_q"] = pd.qcut(t.svi_overall, 4, labels=["Q1 least", "Q2", "Q3", "Q4 most"])
    for col in ["housing_transport_q", "svi_q", "ur_class", "tribal_any", "region"]:
        k = t.groupby(col, observed=True).apply(lambda x: pd.Series({
            "tracts": len(x), "real_stops": x.real.sum(),
            "missing_share": 1 - x.mapped.sum() / x.real.sum(),
            "tracts_all_missing": (x.mapped == 0).mean()}), include_groups=False)
        print(f"\n-- by {col}\n{k.round(3).to_string()}")


if __name__ == "__main__":
    main()
