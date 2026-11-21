"""Ways out of each tract: public roads that genuinely cross the tract edge, Overture vs Census TIGER.

Tract edges are drawn along TIGER roads, and Overture's copy of such a road sits a few metres off,
so it zig-zags across the edge. A naive crossing count would hand Overture dozens of fake exits.
Instead exits are counted on two rings, BAND metres inside and outside the edge, and the smaller
count is kept.

    uv run python experiments/evacuation_exits.py [--band=30] northern-ca [maricopa-az ...]
"""
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

BAND = 30
ALBERS = "EPSG:5070"
OV_CLASSES = ["motorway", "trunk", "primary", "secondary", "tertiary", "residential", "unclassified"]
# primary, secondary, local roads and ramps; 4WD trails and private roads are left out as not evacuation routes
TIGER_CLASSES = ["S1100", "S1200", "S1400", "S1630"]


def ring_hits(rings, roads, snap=10):
    """Distinct points (snapped to `snap` m) where roads cross each ring."""
    ring = gpd.GeoDataFrame({"GEOID": rings.index}, geometry=rings.to_numpy(), crs=roads.crs)
    pairs = gpd.sjoin(roads[["geometry"]], ring, predicate="intersects")
    pts = shapely.intersection(pairs.geometry.to_numpy(), ring.set_index("GEOID").geometry.loc[pairs.GEOID].to_numpy())
    p = gpd.GeoDataFrame({"GEOID": pairs.GEOID.to_numpy()}, geometry=pts).explode(index_parts=False)
    p = p[p.geom_type == "Point"]
    p["key"] = (p.geometry.x // snap).astype("int64").astype(str) + "_" + (p.geometry.y // snap).astype("int64").astype(str)
    return p.drop_duplicates(["GEOID", "key"]).groupby("GEOID").size()


def exits(tracts, roads):
    """Edge crossings per tract: a crossing road hits both a ring BAND m inside the edge and one BAND m outside,
    while a road hugging the edge hits neither."""
    g = tracts.set_index("GEOID").geometry
    inner = ring_hits(g.buffer(-BAND).boundary, roads).reindex(g.index, fill_value=0)
    outer = ring_hits(g.buffer(BAND).boundary, roads).reindex(g.index, fill_value=0)
    return pd.concat([inner, outer], axis=1).min(axis=1)


def region(r):
    d = Path("data/cache") / r
    sub = pd.read_csv(d / "sample-submission.csv", dtype=str).GEOID
    tracts = gpd.read_parquet(d / "tracts.parquet").set_crs("OGC:CRS84", allow_override=True)
    tracts = tracts[tracts.GEOID.isin(sub)].to_crs(ALBERS).reset_index(drop=True)

    def load(f, col, keep):
        g = gpd.read_parquet(d / f, columns=[col, "geometry"])
        return g[g[col].isin(keep)].set_crs("OGC:CRS84", allow_override=True).to_crs(ALBERS)

    ov = load("ov_roads_all.parquet", "class", OV_CLASSES)
    track = load("ov_roads_other.parquet", "class", ["track"])
    minor = load("ov_roads_other.parquet", "class", ["service", "unknown", "living_street"])
    t0 = time.time()
    out = pd.DataFrame({"GEOID": tracts.GEOID, "region": r,
                        "exits_tiger": exits(tracts, load("tiger_roads_all.parquet", "MTFCC", TIGER_CLASSES)).to_numpy(),
                        "exits_overture": exits(tracts, ov).to_numpy(),
                        # the same count once Overture's unpaved "track" roads are admitted, then service roads too
                        "exits_overture_track": exits(tracts, pd.concat([ov, track])).to_numpy(),
                        "exits_overture_all": exits(tracts, pd.concat([ov, track, minor])).to_numpy()})
    print(f"{r}: {len(out)} tracts, {time.time() - t0:.0f} s", flush=True)
    out.to_csv(d / ("exits.csv" if BAND == 30 else f"exits_b{BAND}.csv"), index=False)
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0].startswith("--band="):
        BAND = int(args.pop(0).split("=")[1])
    for r in args:
        region(r)
