"""True centroids for buildings whose bbox crosses a tract edge, the only ones where
bbox centre and centroid can land in different tracts. Streams the full outlines once.

    uv run python src/fetch_centroids.py northern-ca eastern-ok ...
"""
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

from fetch import BUCKET, connect

SOURCES = {"ov_buildings": "overture-buildings", "ms_buildings": "microsoft-buildings"}
KEY = ["xmin", "ymin", "xmax", "ymax"]


def straddlers(tracts, b, chunk=1_000_000):
    """Rows whose bbox is not inside a single tract."""
    keep = []
    for i in range(0, len(b), chunk):
        part = b.iloc[i:i + chunk]
        boxes = gpd.GeoDataFrame(geometry=shapely.box(*(part[c].to_numpy() for c in KEY)),
                                 index=part.index, crs=tracts.crs)
        inside = gpd.sjoin(boxes, tracts[["geometry"]], predicate="within").index.unique()
        keep.append(part.loc[~part.index.isin(inside), KEY])
    return pd.concat(keep).drop_duplicates()


def fetch(region):
    d = Path("data/cache") / region
    tracts = gpd.read_parquet(d / "tracts.parquet").set_crs("OGC:CRS84", allow_override=True)
    con = connect()
    for layer, src in SOURCES.items():
        dest = d / f"{layer}_straddle_centroids.parquet"
        if dest.exists():
            continue
        t = time.time()
        s = straddlers(tracts, pd.read_parquet(d / f"{layer}.parquet", columns=KEY))
        con.register("s", s)
        # bbox is the join key because Microsoft rows carry no id
        con.sql(f"""COPY (SELECT b.bbox.xmin AS xmin, b.bbox.ymin AS ymin, b.bbox.xmax AS xmax, b.bbox.ymax AS ymax,
                          ST_X(ST_Centroid(b.geometry)) AS cx, ST_Y(ST_Centroid(b.geometry)) AS cy
                   FROM '{BUCKET}/reference/{region}/{region}-{src}.parquet' b
                   SEMI JOIN s ON b.bbox.xmin = s.xmin AND b.bbox.ymin = s.ymin
                              AND b.bbox.xmax = s.xmax AND b.bbox.ymax = s.ymax)
                   TO '{dest}.tmp' (FORMAT parquet)""")
        Path(f"{dest}.tmp").rename(dest)
        n = con.sql(f"SELECT count(*) FROM '{dest}'").fetchone()[0]
        print(f"{region} {layer}: {len(s):,} straddlers, {n:,} centroids, {time.time() - t:.0f} s", flush=True)


if __name__ == "__main__":
    for r in sys.argv[1:]:
        fetch(r)
