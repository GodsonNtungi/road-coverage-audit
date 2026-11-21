"""Coverage gap score per tract, from data/cache/<region>/.

    uv run python src/score.py northern-ca [--edge both|first]
"""
import argparse
from pathlib import Path

import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd

SCHOOL_CATS = {"elementary_school", "middle_school", "high_school", "school", "private_school", "public_school"}
HIFLD_CATS = {"fire": {"fire_department"}, "ems": {"ambulance_and_ems_services"}, "schools": SCHOOL_CATS}
# published tracts with no road component, used as a self-check
NO_ROAD = {"eastern-ok": 253, "maricopa-az": 869, "northern-ca": 218, "south-central-tx": 1704}


def gap(have, ref):
    """1 - min(1, have/ref); NaN where there is no reference."""
    ref = np.asarray(ref, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(ref > 0, 1 - np.minimum(1, np.asarray(have, float) / ref), np.nan)


EDGE = "both"  # a point on a shared tract edge counts in every tract it touches, or "first"
KEY = ["xmin", "ymin", "xmax", "ymax"]


def centres(df):
    return (df.xmin.to_numpy() + df.xmax.to_numpy()) / 2, (df.ymin.to_numpy() + df.ymax.to_numpy()) / 2


def building_centres(d, layer):
    """Bbox centres, replaced by true centroids for the edge-crossing buildings where fetched."""
    b = pd.read_parquet(d / f"{layer}.parquet", columns=KEY)
    b["cx"], b["cy"] = centres(b)
    f = d / f"{layer}_straddle_centroids.parquet"
    if f.exists():
        c = pd.read_parquet(f).drop_duplicates(KEY).set_index(KEY)
        b = b.set_index(KEY)
        b.update(c)
        b = b.reset_index()
    return b.cx.to_numpy(), b.cy.to_numpy()


def count_points(tracts, x, y):
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(x, y), crs=tracts.crs)
    hit = gpd.sjoin(pts, tracts[["GEOID", "geometry"]], predicate="intersects", how="inner")
    if EDGE == "first":
        hit = hit[~hit.index.duplicated()]
    return hit.groupby("GEOID").size()


def road_length(region_dir, layer):
    """Clipped road metres per tract, in DuckDB: tracts sit on roads, so edge cases follow its numerics."""
    con = duckdb.connect()
    con.sql("INSTALL spatial; LOAD spatial")
    to_m = "ST_Transform(geometry, 'EPSG:4326', 'EPSG:5070', always_xy := true)"
    return con.sql(f"""
        WITH t AS (SELECT GEOID, {to_m} AS g FROM '{region_dir}/tracts.parquet'),
             x AS (SELECT {to_m} AS g FROM '{region_dir}/{layer}.parquet')
        SELECT t.GEOID, sum(ST_Length(ST_Intersection(t.g, x.g))) AS len
        FROM t JOIN x ON ST_Intersects(t.g, x.g) GROUP BY 1""").df().set_index("GEOID").len


def score(region, cache=Path("data/cache")):
    d = cache / region
    sub = pd.read_csv(d / "sample-submission.csv", dtype={"GEOID": str})[["GEOID"]]
    tracts = gpd.read_parquet(d / "tracts.parquet")
    tracts = tracts[tracts.GEOID.isin(sub.GEOID)].set_crs("OGC:CRS84", allow_override=True)
    out = sub.set_index("GEOID")
    ix = out.index

    ov_len, tg_len = road_length(d, "ov_roads"), road_length(d, "tiger_roads")
    out["transport_gap"] = gap(ov_len.reindex(ix, fill_value=0), tg_len.reindex(ix, fill_value=0))

    ov_b = count_points(tracts, *building_centres(d, "ov_buildings")).reindex(ix, fill_value=0)
    ms_b = count_points(tracts, *building_centres(d, "ms_buildings")).reindex(ix, fill_value=0)
    out["building_gap"] = gap(ov_b, ms_b)

    pois = pd.read_parquet(d / "ov_pois.parquet")
    for kind, cats in HIFLD_CATS.items():
        have = count_points(tracts, *centres(pois[pois.cat.isin(cats)])).reindex(ix, fill_value=0)
        ref = count_points(tracts, *centres(pd.read_parquet(d / f"{kind}.parquet"))).reindex(ix, fill_value=0)
        out[f"poi_gap_{kind}"] = gap(have, ref)
    cbp = pd.read_parquet(d / "cbp.parquet").set_index("GEOID").cbp_estab.reindex(ix, fill_value=0)
    out["poi_gap_cbp"] = gap(count_points(tracts, *centres(pois)).reindex(ix, fill_value=0), cbp)
    hifld = out[["poi_gap_fire", "poi_gap_ems", "poi_gap_schools"]].mean(axis=1)  # skips NaN
    out["poi_gap"] = pd.concat([hifld, out.poi_gap_cbp], axis=1).mean(axis=1)

    out["coverage_gap_score"] = out[["transport_gap", "building_gap", "poi_gap"]].mean(axis=1)
    out["region"] = region
    return out.reset_index()


def check(region, s):
    none_road = s.transport_gap.isna().sum()
    any_undef = s[["transport_gap", "building_gap", "poi_gap"]].isna().any(axis=1).mean()
    print(f"{region}: {len(s)} tracts, no road {none_road} (published {NO_ROAD[region]}), "
          f"any undefined {any_undef:.3f}, mean score {s.coverage_gap_score.mean():.6f}")
    assert s.coverage_gap_score.notna().all()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("regions", nargs="+")
    ap.add_argument("--edge", default="both", choices=["both", "first"])
    a = ap.parse_args()
    EDGE = a.edge
    for r in a.regions:
        s = score(r)
        check(r, s)
        centroids = all((Path("data/cache") / r / f"{l}_straddle_centroids.parquet").exists()
                        for l in ("ov_buildings", "ms_buildings"))
        s.to_csv(Path("data/cache") / r / f"scores_{a.edge}_duckroads{'_centroid' if centroids else ''}.csv",
                 index=False)
