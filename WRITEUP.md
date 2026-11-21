# One road out: the escape-route map hides a quarter of the ways out of rural and tribal neighbourhoods

**Author:** GodsonNtungi
**Written for:** the Bias Bounty Mapping Equity Challenge, Best Bias Discovery (Part 1) and Best Documentation (Part 2)
**Best rebuild of the hidden score:** public RMSE 4.5e-8 (4.7e-8 with roads computed on linux/arm64)
**Data:** challenge package only, Overture release 2026-08-19.0. One external source (transit agency GTFS feeds) was used for a test that came back negative; it is documented in Part 1, section 6.

---

## Part 1: Best Bias Discovery

### 1. The finding

When a fire, flood or chemical release forces people out, the question a map has to answer is simple: **how many roads lead out of this neighbourhood?**

We counted the ways out of every scored tract twice. Once on Census TIGER roads, and once on the challenge's own Overture road layer (`<region>-overture-roads.parquet`, which the data README describes as the **escape-route** layer: drivable classes, with service and pedestrian ways dropped).

| | Tracts | Real ways out (TIGER) | Hidden from the escape-route layer | Share hidden |
|---|---:|---:|---:|---:|
| Rural | 1,712 | 100,223 | 24,314 | **24%** |
| Urban | 7,653 | 198,787 | 10,322 | 5% |
| Tribal (any overlap) | 858 | 38,879 | 7,335 | **19%** |
| All scored tracts | 9,365 | 299,010 | 34,636 | 12% |

Averaged per tract, a rural tract is missing 19.4% of its ways out against 4.4% for an urban tract, and a tribal tract 14.5% against 6.4%.

**221 tracts, home to 635,069 people, show half or fewer of their real ways out.** 143 of them are rural and 33 are tribal.

### 2. Why the scorecard cannot see this

The scored road component compares **named highways only** (TIGER S1100/S1200 against Overture motorway, trunk, primary and secondary). It measures whether the big roads exist, and says nothing about the local roads that connect a neighbourhood to them. It is also undefined for the 3,044 tracts (32%) that have no named highway at all.

Our scorecard for the best rebuild reads rural vs urban 2.33x, tribal vs non-tribal 2.90x, wildfire hazard 1.75x. Those are disparities in highway length, buildings and facilities. **Ways out is a different quantity**, computed from roads the score never looks at, so no stratification of the five scorecard metrics can produce it. It is also a quantity the scorecard's own road term cannot reach: 51 of the 221 half-hidden tracts have no named highway, so their road term is undefined and the composite never mentions roads at all.

### 3. What is going on: two mechanisms of about equal size

**(a) The roads exist, but are filed as "track".** Overture carries many rural roads with class `track`, the OpenStreetMap tag for unpaved or agricultural roads. TIGER records the same roads as ordinary local roads (S1400). The escape-route layer drops `track`, so these ways out disappear from it.

**(b) The roads are not in Overture at all.** Even after adding every Overture `track` back, rural tracts still miss more ways out than urban ones.

| Share of ways out not shown, per tract | Escape-route layer | + Overture `track` roads |
|---|---:|---:|
| Rural | 19.4% | 8.9% |
| Urban | 4.4% | 3.7% |
| Tribal | 14.5% | 9.8% |
| Non-tribal | 6.4% | 4.1% |
| High wildfire hazard (top quarter within region) | 12.2% | 6.1% |
| Low wildfire hazard (bottom quarter) | 4.8% | 4.2% |

About half of the rural gap is labelling, and half is roads that are genuinely missing.

Figure `viz/exits_examples.png` shows both. In Napa County, the San Carlos Reservation and Lookout Rancheria, the orange Overture `track` lines sit exactly on the grey TIGER roads: present, but filed outside the escape-route layer. In the Kiowa-Comanche-Apache-Fort Sill Apache area of Oklahoma, grey TIGER roads have no Overture road of any class beside them.

### 4. Where, and who

**Named tracts.** High wildfire hazard, largest share of ways out hidden from the escape-route layer:

| Tract | Place | Ways out: TIGER | Escape-route layer | With tracks | People |
|---|---|---:|---:|---:|---:|
| 06055201800 | Napa County, CA | 24 | 2 | 37 | 1,781 |
| 48443950100 | Terrell County, TX | 75 | 7 | 79 | 760 |
| 48383950100 | Reagan County, TX | 187 | 20 | 144 | 3,385 |
| 06049000200 | Modoc County, CA (Lookout Rancheria) | 177 | 33 | 169 | 1,511 |
| 40031002401 | Comanche County, OK (Kiowa-Comanche-Apache-Fort Sill Apache OTSA) | 87 | 18 | 51 | 295 |
| 04009940500 | Graham County, AZ (San Carlos Reservation) | 47 | 12 | 79 | 4,720 |
| 06063000100 | Plumas County, CA | 38 | 8 | 64 | 5,271 |

**Tribal land by region.**

| Region | Tribal tracts | Hidden from escape-route layer | With tracks |
|---|---:|---:|---:|
| Maricopa region (Navajo, Tohono O'odham, Fort Apache, Gila River, San Carlos, Salt River) | 37 | 34.4% | 4.1% |
| Northern California | 15 | 25.2% | 2.3% |
| Eastern Oklahoma | 805 | 13.3% | 10.2% |

In Arizona and California the tribal gap is almost entirely the `track` label. In Eastern Oklahoma a real gap remains after tracks are added.

**Social vulnerability shows no difference** (7.3% in tracts with SVI 0.75 or higher, against 7.1% elsewhere). We report that rather than leave it out.

### 5. Why it matters

- **Evacuation routing.** A routing engine or evacuation planner that loads the escape-route layer sees 2 ways out of Napa tract 06055201800, where the Census records 24. A neighbourhood that looks like a dead end on the map gets planned as one: fewer exit routes, heavier queues on the one road shown, and contraflow or shelter-in-place decisions made on a false picture.
- **Where it lands.** The hidden exits sit in rural and tribal tracts, where distances are long, alternatives are few, and wildfire hazard is highest. High-hazard tracts hold 9.6 million people, and the escape-route layer hides 19,179 of their 106,887 ways out.
- **Two different fixes.** The labelling half is cheap: an evacuation layer should include `track` roads, flagged as unpaved rather than dropped. The missing half needs mapping work, and the tract list in `experiments/exits_all.csv` says where: it is concentrated in Eastern Oklahoma, where 13.8% of ways out are missing in the highest-hazard quarter even with tracks included, against 5.8% in the lowest.

### 6. How solid it is

- **Measurement.** A way out is a road crossing the tract edge. Tract edges are drawn along TIGER roads, and Overture's copy of such a road sits a few metres off and zig-zags across the edge, so naive crossing counts give Overture dozens of fake exits. We count crossings on two rings instead, 30 m inside and 30 m outside the edge, and keep the smaller count. A road that hugs the edge crosses neither ring.
- **Band width.** At 20 m, 30 m and 50 m every gap keeps its size and direction (rural 18.5 / 19.4 / 20.6% against urban 4.0 / 4.4 / 4.9%). File: `experiments/evacuation_band_sensitivity.txt`.
- **Label shuffles, 5,000 draws, seed 20260924.** Shuffled within region and, separately, within county.
  - Rural gap: survives both, on both layers (p = 0.0002).
  - Tribal gap on the escape-route layer: survives both (p = 0.0002).
  - **Tribal gap after adding tracks does not survive within-county shuffling (p = 0.85).** Tribal tracts sit in counties where every tract's roads are worse mapped. We do not claim a tribal-specific gap in missing roads beyond that.
  - File: `experiments/evacuation_permutation.txt`.
- **Wildfire is mostly rurality.** Within rural tracts there is no wildfire gradient (21% in the middle quarters, 18% in the top quarter), so we do not claim wildfire hazard as a separate cause. It matters because that is where the hidden exits are, not because hazard predicts them.
- **Reference.** TIGER is a reference, not ground truth. Some S1400 roads may be private or seasonal. That affects both groups, and the rural/urban split survives comparison within the same county.

**Tested and dropped** (reported so the result is not a survivor of hidden tries):

- **Phantom facilities.** 7.0% of Overture fire-station records (243 of 3,462) are closed, duplicated or not fire stations at all: tire shops, a florist, a financial adviser and a domestic-violence hotline are filed as fire or EMS stations and counted as coverage. Once the test is strict, there is no rural, tribal or SVI pattern. Script: `experiments/facility_credibility.py`.
- **Transit stops.** Against 17 agency GTFS feeds (external data, retrieved 2026-09-24, URLs in `experiments/gtfs_sources.txt`), 93% of 40,825 real stops are in Overture, and the most transport-vulnerable tracts miss fewer stops (5.9%) than the least (7.9%). No disparity. Script: `experiments/transit_gap.py`.

### 7. Reproducing Part 1

```
uv run python src/fetch.py <regions>                   # adds ov_roads_all, tiger_roads_all, ov_roads_other
uv run python experiments/evacuation_exits.py <regions>          # ways out per tract, 30 m band
uv run python experiments/evacuation_exits.py --band=20 <regions>
uv run python experiments/evacuation_exits.py --band=50 <regions>
uv run python experiments/evacuation_report.py         # all tables above
uv run python experiments/evacuation_permutation.py    # shuffle tests
uv run python experiments/exits_figure.py              # viz/exits_examples.png
```

Road classes. Overture escape-route layer: motorway, trunk, primary, secondary, tertiary, residential, unclassified. Overture tracks: class `track` from the unfiltered layer. TIGER: S1100, S1200, S1400, S1630. Projection: EPSG:5070.

---

## Part 2: Best Documentation

### 1. The score in one picture (a real tract: 40001376600, Adair County, OK)

```
 gap = 1 - min(1, Overture / reference)      reference = 0  ->  undefined, left out

 ROADS      Overture motorway..secondary 20,019.8 m / TIGER S1100+S1200 20,333.0 m  -> 0.015402
 BUILDINGS  Overture 2,218 / Microsoft 2,249 (counted by centroid)                -> 0.013784
 PLACES     facilities half: fire 1/1 -> 0, EMS 0/0 -> undefined, schools 2/3 -> 0.333333
                             mean of defined = 0.166667
            business half:   all Overture places 50 / CBP 17.684 -> min(1, 2.83) -> 0
            places = mean(0.166667, 0)                                            -> 0.083333

 SCORE      mean of defined parts = (0.015402 + 0.013784 + 0.083333) / 3         =  0.037506
```

### 2. Rules we implemented, each confirmed on the public board

| Change | Public RMSE after |
|---|---:|
| Start: roads clipped with shapely in EPSG:5070, buildings by bbox centre, full precision | 3.821e-6 |
| Round each part to 6 decimals, then the mean to 6 decimals | 3.725e-6 |
| (tested) Round the final score to 5 decimals instead | 5.064e-6, rejected |
| A point exactly on a shared tract edge counts in **both** tracts (what `ST_Intersects` does) | 3.329e-6 |
| Road clipping done in DuckDB spatial instead of shapely | 4.45e-7 |
| True centroids for the 28,786 buildings whose bbox crosses a tract edge | 4.7e-8 |
| Place sub-scores also rounded to 6 decimals before averaging | 4.5e-8 |
| Road step on linux/arm64, DuckDB 1.5.4 | 4.7e-8, see section 4 |

### 3. Edge cases

- **Undefined is not zero.** A part with no reference is left out of the mean. The divisor is 1, 2 or 3: 6,324 tracts have all three parts, 3,028 have two, 27 have one. Road part undefined in 3,044 tracts (253 / 869 / 218 / 1,704, matching the README); building part in 6; places part in 32.
- **Surplus is clipped.** More Overture features than reference gives 0, never a negative gap.
- **Zero Overture, some reference** gives 1: two water tracts, 48039990000 (1 Microsoft building) and 48057990000 (48).
- **Zero-population tracts** are scored like any other. Population is not in the formula.
- **Water tracts.** The 7 south-central-tx tracts ending 99xx0000 that have nothing to score are not in the sample submission. The tract list comes from the sample submission, not the geometry file (6,010 shapes, 6,003 scored).
- **GEOID is text.** Maricopa is state 04, and one New Mexico tract (35023970000) is scored with it.
- **Submit two columns only.** The scorer reads the second column. Optional component columns placed first break the score.

### 4. The numerics trap, and one tract where it decides the answer

Many roads lie exactly on tract edges, because OpenStreetMap roads imported from TIGER keep TIGER's coordinates and tract edges follow TIGER roads. After projecting to EPSG:5070, such a road piece lands a hair inside or outside the tract depending on the last bit of floating-point arithmetic. wangwu (thread 34972) showed that the reference was computed with DuckDB on ARM Linux.

We ran the road step both on macOS arm64 (DuckDB 1.5.5) and on linux/arm64 (DuckDB 1.5.4, under emulation). Road lengths differ in the last digits in 486 tracts. After rounding, exactly one tract changes: **48121021739 (Denton County, TX)**, where a 54 m Overture segment on the tract edge counts inside on macOS and outside on Linux. Its score moves from 0.004361 to 0.005585. The public RMSE did not change, so this tract is in the private split. We selected the Linux file for the private leaderboard.

### 5. Checks anyone can run

- **README anchors.** Tracts with no road part: 253 / 869 / 218 / 1,704. Share with any undefined part: 0.213 / 0.549 / 0.369 / 0.285 (published 21 / 55 / 37 / 28%).
- **The sample file carries the answer's averages.** The placeholder values in `SampleSubmission.csv` are the all-tract means of the reference, with undefined parts counted as 0. Ours reproduce all four exactly: coverage 0.058436, transport 0.111771, building 0.005601, poi 0.051414.
- **Two engines, same counts.** Building, place and facility counts per tract are identical between shapely and DuckDB `ST_Intersects`, and a fully DuckDB rebuild with centroids from the complete outlines reproduces every tract.
- **Bounding boxes of points are exact.** For Overture places and USGS fire stations, the parquet `bbox` equals the point exactly (checked on 20,561 Northern California rows), so bbox centres can stand in for the geometry.

### 6. Traps worth knowing

- **Axis order.** Pass `always_xy := true` to `ST_Transform`, or everything becomes `inf`.
- **Spatial LEFT JOIN.** In DuckDB it can silently drop tracts with no match (thread 34901). Inner join, then attach to the tract list by GEOID.
- **Reading only what you need.** The whole score needs about 1.4 GB of the 8 GB package: bbox columns for buildings, class-filtered roads, and point columns for places. Only the ~0.1% of buildings whose bbox crosses a tract edge need their outline, for the centroid.

### 7. Reproducing Part 2

```
uv run python src/fetch.py northern-ca eastern-ok maricopa-az south-central-tx
uv run python src/fetch_centroids.py <regions>         # centroids of edge-crossing buildings
uv run python src/score.py <regions>                   # scores_both_duckroads_centroid.csv
docker run --rm --platform linux/arm64 -v "$PWD":/w -w /w python:3.12-slim \
  sh -c "pip install -q duckdb==1.5.4 && python src/roads_linux.py"
uv run python src/apply_linux_roads.py
uv run python src/make_submission.py round6 both linuxroads_centroid
```

Seeds are fixed where randomness is used (shuffle tests only). No model, no training.
