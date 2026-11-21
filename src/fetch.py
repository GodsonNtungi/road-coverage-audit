"""Pull only the columns the score needs from the bucket into data/cache/<region>/.

    uv run python src/fetch.py northern-ca
"""
import sys
import time
from pathlib import Path

import duckdb

BUCKET = "s3://us-west-2.opendata.source.coop/humane-intelligence/bias-bounty-mapping-equity-challenge"
BBOX = "bbox.xmin AS xmin, bbox.ymin AS ymin, bbox.xmax AS xmax, bbox.ymax AS ymax"

# name -> (source file, select list, where clause)
LAYERS = {
    "tracts": ("strata/{r}/{r}-census-tracts.parquet", "GEOID, geometry", "TRUE"),
    "ov_buildings": ("reference/{r}/{r}-overture-buildings.parquet", f"id, {BBOX}", "TRUE"),
    "ms_buildings": ("reference/{r}/{r}-microsoft-buildings.parquet", BBOX, "TRUE"),
    "ov_roads": ("reference/{r}/{r}-overture-roads.parquet", "id, class, geometry",
                 "class IN ('motorway','trunk','primary','secondary')"),
    "tiger_roads": ("reference/{r}/{r}-census-tiger-roads.parquet", "LINEARID, MTFCC, geometry",
                    "MTFCC IN ('S1100','S1200')"),
    "ov_pois": ("reference/{r}/{r}-overture-pois.parquet", f"id, categories.primary AS cat, {BBOX}", "TRUE"),
    # writeup only, not used by the score
    "ov_pois_detail": ("reference/{r}/{r}-overture-pois.parquet",
                       "id, categories.primary AS cat, basic_category, names.primary AS name, confidence, "
                       "operating_status, list_transform(sources, s -> s.dataset) AS datasets, "
                       f"list_transform(sources, s -> s.update_time) AS update_times, {BBOX}", "TRUE"),
    "transit": ("reference/{r}/{r}-overture-infrastructure.parquet", "id, class, subtype, names.primary AS name, geometry", "TRUE"),
    "ov_roads_all": ("reference/{r}/{r}-overture-roads.parquet",
                     "id, class, list_transform(connectors, c -> c.connector_id) AS connector_ids, geometry", "TRUE"),
    "tiger_roads_all": ("reference/{r}/{r}-census-tiger-roads.parquet", "LINEARID, MTFCC, geometry", "TRUE"),
    "ov_roads_other": ("reference/{r}/{r}-overture-roads-unfiltered.parquet", "id, class, geometry",
                       "class NOT IN ('motorway','trunk','primary','secondary','tertiary','residential','unclassified')"),
    "fire": ("reference/{r}/{r}-hifld-fire-stations.parquet", BBOX, "TRUE"),
    "ems": ("reference/{r}/{r}-hifld-ems-stations.parquet", BBOX, "TRUE"),
    "schools": ("reference/{r}/{r}-hifld-schools.parquet", BBOX, "TRUE"),
    "cbp": ("reference/{r}/{r}-census-cbp.parquet", "GEOID, cbp_estab, cbp_estab_bus, cbp_estab_res", "TRUE"),
}


def connect():
    con = duckdb.connect()
    for s in ["INSTALL httpfs", "LOAD httpfs", "INSTALL spatial", "LOAD spatial",
              "SET s3_region='us-west-2'", "SET s3_url_style='path'"]:
        con.sql(s)
    return con


def fetch(region):
    out = Path("data/cache") / region
    out.mkdir(parents=True, exist_ok=True)
    con = connect()
    sample = out / "sample-submission.csv"
    if not sample.exists():  # the https proxy 403s Python's user agent, so go through s3
        con.sql(f"COPY (SELECT * FROM read_csv('{BUCKET}/reference/{region}/{region}-sample-submission.csv', "
                f"all_varchar=true)) TO '{sample}' (HEADER)")
    for name, (src, cols, where) in LAYERS.items():
        dest = out / f"{name}.parquet"
        if dest.exists():
            continue
        t = time.time()
        con.sql(f"COPY (SELECT {cols} FROM '{BUCKET}/{src.format(r=region)}' WHERE {where}) "
                f"TO '{dest}.tmp' (FORMAT parquet, COMPRESSION zstd)")
        Path(f"{dest}.tmp").rename(dest)  # a killed run never leaves a half file that looks done
        n = con.sql(f"SELECT count(*) FROM '{dest}'").fetchone()[0]
        print(f"{name:13s} {n:>9,} rows  {dest.stat().st_size / 1e6:7.1f} MB  {time.time() - t:6.1f} s", flush=True)


if __name__ == "__main__":
    for r in sys.argv[1:]:
        fetch(r)
