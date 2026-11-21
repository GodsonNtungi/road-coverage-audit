"""Road metres per tract on linux/arm64 DuckDB 1.5.4, where the reference numerics come from.
macOS libm differs in the last bit, which flips roads lying exactly on tract edges.

    docker run --rm --platform linux/arm64 -v "$PWD":/w -w /w python:3.12-slim \
      sh -c "pip install -q duckdb==1.5.4 && python src/roads_linux.py"
"""
import duckdb

REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]
TO_M = "ST_Transform(geometry, 'EPSG:4326', 'EPSG:5070', always_xy := true)"

con = duckdb.connect()
con.sql("INSTALL spatial; LOAD spatial")
for r in REGIONS:
    d = f"data/cache/{r}"
    for layer, col in [("ov_roads", "ov_len"), ("tiger_roads", "tg_len")]:
        con.sql(f"""COPY (
            WITH t AS (SELECT GEOID, {TO_M} AS g FROM '{d}/tracts.parquet'),
                 x AS (SELECT {TO_M} AS g FROM '{d}/{layer}.parquet')
            SELECT t.GEOID, sum(ST_Length(ST_Intersection(t.g, x.g))) AS {col}
            FROM t JOIN x ON ST_Intersects(t.g, x.g) GROUP BY 1)
            TO '{d}/{col}_linux.csv' (HEADER)""")
    print(r, "done", flush=True)
