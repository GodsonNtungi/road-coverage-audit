"""Every count behind the score done in DuckDB (ARM), the way the reference appears to have been built:
building centroids from the full outlines, points and roads joined with ST_Intersects.

Writes data/cache/<region>/counts_duckdb.csv and scores_pureduck.csv.

    uv run python src/reference_duckdb.py northern-ca [...]
"""
import sys
import time
from pathlib import Path

import pandas as pd

from fetch import BUCKET, connect
from score import HIFLD_CATS, gap, road_length

TO_M = "ST_Transform(geometry, 'EPSG:4326', 'EPSG:5070', always_xy := true)"


def counts(con, d, points_sql, name):
    # inner join, then attach to the tract list: a spatial LEFT JOIN drops unmatched tracts
    return con.sql(f"""
        WITH t AS (SELECT GEOID, geometry AS g FROM '{d}/tracts.parquet'), p AS ({points_sql})
        SELECT t.GEOID, count(*) AS {name} FROM t JOIN p ON ST_Intersects(t.g, p.g) GROUP BY 1""").df().set_index("GEOID")[name]


def region(r):
    d = Path("data/cache") / r
    con = connect()
    sub = pd.read_csv(d / "sample-submission.csv", dtype={"GEOID": str}).GEOID
    f = d / "counts_duckdb.csv"
    if f.exists():
        c = pd.read_csv(f, dtype={"GEOID": str}).set_index("GEOID")
    else:
        t0 = time.time()
        cols = {}
        for name, src in [("ov_b", "overture-buildings"), ("ms_b", "microsoft-buildings")]:
            cols[name] = counts(con, d, f"SELECT ST_Centroid(geometry) AS g FROM '{BUCKET}/reference/{r}/{r}-{src}.parquet'", name)
            print(f"  {r} {name} {time.time() - t0:.0f} s", flush=True)
        pois = f"'{d}/ov_pois.parquet'"
        ctr = "ST_Point((xmin + xmax) / 2, (ymin + ymax) / 2)"  # bbox of a point is the point, checked exactly
        cols["pois_all"] = counts(con, d, f"SELECT {ctr} AS g FROM {pois}", "pois_all")
        for kind, cats in HIFLD_CATS.items():
            inlist = ", ".join(f"'{c}'" for c in cats)
            cols[f"ov_{kind}"] = counts(con, d, f"SELECT {ctr} AS g FROM {pois} WHERE cat IN ({inlist})", f"ov_{kind}")
            cols[f"ref_{kind}"] = counts(con, d, f"SELECT {ctr} AS g FROM '{d}/{kind}.parquet'", f"ref_{kind}")
        c = pd.DataFrame(cols).reindex(sub, fill_value=0).fillna(0).astype(int)
        c["ov_len"] = road_length(d, "ov_roads").reindex(sub, fill_value=0)
        c["tg_len"] = road_length(d, "tiger_roads").reindex(sub, fill_value=0)
        c.index.name = "GEOID"
        c.to_csv(f)
    cbp = pd.read_parquet(d / "cbp.parquet").set_index("GEOID").cbp_estab.reindex(c.index, fill_value=0)
    out = pd.DataFrame(index=c.index)
    out["transport_gap"] = gap(c.ov_len, c.tg_len)
    out["building_gap"] = gap(c.ov_b, c.ms_b)
    for kind in HIFLD_CATS:
        out[f"poi_gap_{kind}"] = gap(c[f"ov_{kind}"], c[f"ref_{kind}"])
    out["poi_gap_cbp"] = gap(c.pois_all, cbp)
    hifld = out[["poi_gap_fire", "poi_gap_ems", "poi_gap_schools"]].mean(axis=1)
    out["poi_gap"] = pd.concat([hifld, out.poi_gap_cbp], axis=1).mean(axis=1)
    out["coverage_gap_score"] = out[["transport_gap", "building_gap", "poi_gap"]].mean(axis=1)
    out["region"] = r
    out.reset_index().to_csv(d / "scores_pureduck.csv", index=False)
    print(f"{r}: done", flush=True)


if __name__ == "__main__":
    for r in sys.argv[1:]:
        region(r)
