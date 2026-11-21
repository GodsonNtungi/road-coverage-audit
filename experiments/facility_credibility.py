"""Does the scored map count fire/EMS stations that are not really there, and where?

For every tract with a reference fire station, recount Overture's fire stations using only
credible records (open, not a duplicate, named like a station; low confidence reported separately) and
compare the groups whose apparent coverage evaporates.

    uv run python experiments/facility_credibility.py
"""
import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from score import centres  # noqa: E402

REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]
CATS = {"fire": "fire_department", "ems": "ambulance_and_ems_services"}
LOW_CONF = 0.5
# A record is only called fake when its name says it is something else; ambiguous names count as real.
# STRONG: not a station even if the name mentions fire/EMS (a fire museum, a 911 centre, an extinguisher shop).
STRONG_NOT = re.compile(
    r"museum|training|academy(?! vfd)|extinguisher|\bsales\b|equipment|systems|pension|relief fund|retirement|consultant|"
    r"dispatch|9-?1-?1|call center|administrat|billing|industries|\btires?\b|florist|financial|edward jones|"
    r"tooth|dental|hearing|midwi|homebirth|pregnancy|medspa|happiness|construction|research|technolog|tronics|"
    r"chimney|plumbing|restoration|legal|animal control|public works|nursing|diagnostic|imaging|workforce|"
    r"hot ?line|marketplace|non-emergency|\bm\.?d\b\.?|, ?d\.?o\b|\bdr\.|acnp|faans|firearms|wellness|"
    r"healing|movement laboratory|primary care|care management|pension fund|fund\b", re.I)
# WEAK: only fake when nothing in the name says station
WEAK_NOT = re.compile(r"\bllc\b|\binc\b|\bltd\b|corporation|city of|towne? of|city hall|water|union local|"
                      r"precinct|border patrol|\bdps\b|jbsa|security|supply|detail\b|pack shack|community center|"
                      r"\bwic\b|transit|travel|\bcert\b|citizen corps|shelter seekers|enrichment|addressing", re.I)
STATION = re.compile(r"fire|vfd|rescue|\bems\b|ambulance|station|medic|\besd|bomberos|engine|air evac|"
                     r"careflite|calstar|starflight|life ?flight|air ?med|native air|omniflight|med ?star|"
                     r"acadian|rural\W?metro|air methods|sky ?med|medflight|lifeline|life line|emergency medical|\bsta\.? ?\d", re.I)
DUP_METRES = 100


def tract_of(tracts, df):
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(*centres(df)), crs=tracts.crs)
    return gpd.sjoin(pts, tracts[["GEOID", "geometry"]], predicate="intersects").drop(columns="index_right")


def flag_duplicates(p):
    """True for the 2nd+ record of a station: same tract and within DUP_METRES of an earlier one."""
    m = p.to_crs("EPSG:5070")
    dup = np.zeros(len(m), bool)
    for _, g in m.groupby("GEOID"):
        xy = np.c_[g.geometry.x, g.geometry.y]
        idx = g.index.to_numpy()
        for i in range(1, len(g)):
            if (np.hypot(*(xy[:i] - xy[i]).T) < DUP_METRES).any():
                dup[m.index.get_loc(idx[i])] = True
    return dup


def region_table(r):
    d = Path("data/cache") / r
    tracts = gpd.read_parquet(d / "tracts.parquet").set_crs("OGC:CRS84", allow_override=True)
    sub = pd.read_csv(d / "sample-submission.csv", dtype={"GEOID": str}).GEOID
    tracts = tracts[tracts.GEOID.isin(sub)]
    pois = pd.read_parquet(d / "ov_pois_detail.parquet")
    rows = []
    for kind, cat in CATS.items():
        p = tract_of(tracts, pois[pois.cat == cat]).reset_index(drop=True)
        p["closed"] = p.operating_status.eq("permanently_closed")
        p["low_conf"] = p.confidence < LOW_CONF
        name = p.name.fillna("")
        p["misnamed"] = name.str.contains(STRONG_NOT) | (name.str.contains(WEAK_NOT) & ~name.str.contains(STATION))
        p["duplicate"] = flag_duplicates(p)
        # low confidence is reported but not treated as fake: many low-confidence records are real stations
        p["credible"] = ~(p.closed | p.misnamed | p.duplicate)
        ref = tract_of(tracts, pd.read_parquet(d / f"{kind}.parquet")).groupby("GEOID").size()
        agg = p.groupby("GEOID").agg(listed=("credible", "size"), credible=("credible", "sum"),
                                     closed=("closed", "sum"), low_conf=("low_conf", "sum"),
                                     misnamed=("misnamed", "sum"), duplicate=("duplicate", "sum"))
        t = agg.reindex(sub, fill_value=0)
        t["reference"] = ref.reindex(sub, fill_value=0).to_numpy()
        t["kind"], t["region"] = kind, r
        rows.append(t.reset_index())
        p.drop(columns="geometry").assign(region=r, kind=kind).to_parquet(d / f"credibility_{kind}.parquet")
    return pd.concat(rows)


def gap(have, ref):
    return np.where(ref > 0, 1 - np.minimum(1, have / np.maximum(ref, 1)), np.nan)


if __name__ == "__main__":
    t = pd.concat([region_table(r) for r in REGIONS])
    strata = pd.concat([pd.read_parquet(f"data/strata/{r}/{r}-strata-tract-table.parquet",
                                        columns=["GEOID", "tribal_any", "svi_overall", "ur_class", "pop_total",
                                                 "aiannh_name"]) for r in REGIONS])
    t = t.merge(strata, on="GEOID", how="left")
    t["gap_scored"] = gap(t.listed, t.reference)
    t["gap_credible"] = gap(t.credible, t.reference)
    t["phantom"] = (t.reference > 0) & (t.gap_scored < 1) & (t.gap_credible > t.gap_scored)
    t.to_csv("experiments/facility_credibility_tracts.csv", index=False)

    s = t[t.reference > 0].copy()
    s["svi_high"] = s.svi_overall >= 0.75
    for kind in CATS:
        k = s[s.kind == kind]
        print(f"\n== {kind}: {len(k)} tracts with a reference station; "
              f"{int(k.listed.sum())} Overture records, {int(k.credible.sum())} credible "
              f"(closed {int(k.closed.sum())}, low-conf {int(k.low_conf.sum())}, "
              f"misnamed {int(k.misnamed.sum())}, duplicate {int(k.duplicate.sum())})")
        for col in ["tribal_any", "svi_high", "ur_class"]:
            g = k.groupby(col).agg(tracts=("GEOID", "size"), phantom_share=("phantom", "mean"),
                                   gap_scored=("gap_scored", "mean"), gap_credible=("gap_credible", "mean"),
                                   people_phantom=("pop_total", lambda x: x[k.loc[x.index, "phantom"]].sum()))
            print(g.round(3).to_string())
