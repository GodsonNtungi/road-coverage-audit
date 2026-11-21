"""Write viz/coverage_map.html: every scored tract coloured by its coverage gap.

    uv run python experiments/make_map.py
"""
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

REGIONS = {"northern-ca": "Northern California", "maricopa-az": "Phoenix area",
           "eastern-ok": "Eastern Oklahoma", "south-central-tx": "South-Central Texas"}
LAYERS = ["coverage_gap_score", "transport_gap", "building_gap", "poi_gap"]


def features():
    rows = []
    for r in REGIONS:
        d = Path("data/cache") / r
        s = pd.read_csv(d / "scores_both_duckroads_centroid.csv", dtype={"GEOID": str})
        s["coverage_gap_score"] = s[["transport_gap", "building_gap", "poi_gap"]].round(6).mean(axis=1)
        st = pd.read_parquet(f"data/strata/{r}/{r}-strata-tract-table.parquet",
                             columns=["GEOID", "pop_total", "svi_overall", "ur_class", "tribal_any", "aiannh_name"])
        t = gpd.read_parquet(d / "tracts.parquet").set_crs("OGC:CRS84", allow_override=True)
        t = t.merge(s, on="GEOID").merge(st, on="GEOID", how="left")
        # ~50 m tolerance keeps the file small; tract shapes stay recognisable at county zoom
        t["geometry"] = t.geometry.simplify(0.0005, preserve_topology=True)
        t["region"] = r
        rows.append(t)
    t = pd.concat(rows)
    cols = ["GEOID", "region", *LAYERS, "pop_total", "svi_overall", "ur_class", "tribal_any", "aiannh_name"]
    t = gpd.GeoDataFrame(t[cols + ["geometry"]], crs="OGC:CRS84")
    for c in LAYERS + ["svi_overall"]:
        t[c] = t[c].round(4)
    gj = json.loads(t.to_json(drop_id=True))
    for f in gj["features"]:  # 4 decimals of a degree is ~10 m, plenty for a tract map
        f["geometry"] = json.loads(json.dumps(f["geometry"]), parse_float=lambda x: round(float(x), 4))
    return gj


def main():
    gj = features()
    html = Path("experiments/map_template.html").read_text()
    html = html.replace("/*DATA*/null", json.dumps(gj, separators=(",", ":"))).replace(
        "/*REGIONS*/null", json.dumps(REGIONS))
    out = Path("viz/coverage_map.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print(out, f"{out.stat().st_size / 1e6:.1f} MB", len(gj["features"]), "tracts")


if __name__ == "__main__":
    main()
