"""Draw example tracts: Census roads vs Overture's drivable layer vs Overture's 'track' roads.

    uv run python experiments/exits_figure.py
"""
import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from evacuation_exits import ALBERS, OV_CLASSES, TIGER_CLASSES  # noqa: E402

EXAMPLES = [("06055201800", "northern-ca", "Napa County, CA"),
            ("04009940500", "maricopa-az", "San Carlos Reservation, AZ"),
            ("06049000200", "northern-ca", "Lookout Rancheria, Modoc County, CA"),
            ("40031002401", "eastern-ok", "Kiowa-Comanche-Apache-Fort Sill Apache OTSA, OK")]
INK = {"tiger": "#b9b8b2", "ov": "#2a78d6", "track": "#eb6834", "edge": "#0b0b0b", "text": "#52514e"}


def layer(d, f, col, keep, clip):
    g = gpd.read_parquet(f"{d}/{f}", columns=[col, "geometry"])
    g = g[g[col].isin(keep)].set_crs("OGC:CRS84", allow_override=True).to_crs(ALBERS)
    return g.clip(clip)


def main():
    fig, axes = plt.subplots(1, len(EXAMPLES), figsize=(4.2 * len(EXAMPLES), 5.2))
    for ax, (geoid, r, label) in zip(axes, EXAMPLES):
        d = f"data/cache/{r}"
        t = gpd.read_parquet(f"{d}/tracts.parquet").set_crs("OGC:CRS84", allow_override=True)
        t = t[t.GEOID == geoid].to_crs(ALBERS)
        view = gpd.GeoDataFrame(geometry=t.buffer(800), crs=ALBERS)
        e = pd.read_csv(f"{d}/exits.csv", dtype={"GEOID": str}).set_index("GEOID").loc[geoid]
        layer(d, "tiger_roads_all.parquet", "MTFCC", TIGER_CLASSES, view).plot(ax=ax, color=INK["tiger"], lw=3.2)
        layer(d, "ov_roads_other.parquet", "class", ["track"], view).plot(ax=ax, color=INK["track"], lw=1.2)
        layer(d, "ov_roads_all.parquet", "class", OV_CLASSES, view).plot(ax=ax, color=INK["ov"], lw=1.2)
        t.boundary.plot(ax=ax, color=INK["edge"], lw=1.4)
        ax.set_axis_off()
        ax.set_anchor("N")
        ax._caption = (f"{label}\ntract {geoid}",
                       f"Ways out:  Census {e.exits_tiger}\n"
                       f"Overture drivable {e.exits_overture}  ·  with tracks {e.exits_overture_track}")
    handles = [plt.Line2D([], [], color=INK["tiger"], lw=3.2, label="Census TIGER road (reference)"),
               plt.Line2D([], [], color=INK["ov"], lw=1.6, label="Overture, drivable classes (escape-route layer)"),
               plt.Line2D([], [], color=INK["track"], lw=1.6, label="Overture, tagged 'track'"),
               plt.Line2D([], [], color=INK["edge"], lw=1.4, label="Tract edge")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=9)
    fig.tight_layout(rect=(0, 0.17, 1, 0.88))
    fig.canvas.draw()
    for ax in axes:  # captions on shared lines: each map keeps its true shape, so axes heights differ
        x = ax.get_subplotspec().get_position(fig).x0 + 0.01
        fig.text(x, 0.97, ax._caption[0], fontsize=10, color="#0b0b0b", va="top")
        fig.text(x, 0.16, ax._caption[1], fontsize=8.5, color=INK["text"], va="top", linespacing=1.5)
    fig.savefig("viz/exits_examples.png", dpi=160, facecolor="#fcfcfb")
    print("viz/exits_examples.png")


if __name__ == "__main__":
    main()
