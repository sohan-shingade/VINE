"""Generate matplotlib figures for the VINE GSoC midterm research report.

Reads the real DVC-pinned snapshots in data/raw/; writes PNGs + base64 files
to $OUT (figs/). All numbers not derived from the snapshots come from the
walk-forward results tables logged to MLflow on 2026-07-08 (see docs/STATE.md).
"""

import base64
import os
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")

OUT = Path(os.environ.get("OUT", "figs"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path("data/raw")

# palette (matches the report)
GREEN = "#2e7a4c"
BLUE = "#31699c"
RED = "#b34a2e"
GOLD = "#96712a"
GREY = "#5b6a5f"
INK = "#1b231d"

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.labelsize": 9,
        "axes.edgecolor": GREY,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#dfe6dc",
        "grid.linewidth": 0.6,
        "xtick.color": INK,
        "ytick.color": INK,
        "text.color": INK,
        "axes.labelcolor": INK,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.dpi": 170,
        "savefig.bbox": "tight",
    }
)


def save(fig, name):
    p = OUT / f"{name}.png"
    fig.savefig(p)
    plt.close(fig)
    (OUT / f"{name}.b64").write_text(base64.b64encode(p.read_bytes()).decode())
    print(f"{name}: {p.stat().st_size / 1024:.0f} KB png")


# ---------------------------------------------------------------- figure 1
# The dataset: real soil-moisture traces, threshold, holdout region, precip.
sensors = ["SE01-LS-1", "SE01-LS-2", "SE01-LS-3", "SE01-LS-4"]
hourly = {}
for s in sensors:
    df = pd.read_parquet(DATA / "sensors" / f"{s}.parquet")
    hourly[s] = df["soil_water"].resample("1h").mean()

weather = pd.read_parquet(DATA / "weather" / "weather_2025-06-03_2026-07-08.parquet")
weather.index = pd.to_datetime(weather.index).tz_localize("UTC")

t0 = min(v.index[0] for v in hourly.values())
t1 = max(v.index[-1] for v in hourly.values())

fig, axes = plt.subplots(
    5,
    1,
    figsize=(7.6, 6.4),
    sharex=True,
    gridspec_kw={"height_ratios": [1, 1, 1, 1, 0.55], "hspace": 0.18},
)
for ax, s in zip(axes[:4], sensors, strict=True):
    y = hourly[s]
    mid = y.index[len(y) // 2]
    ax.axvspan(mid, t1, color=GREY, alpha=0.10, lw=0)
    ax.plot(y.index, y.values, color=BLUE, lw=0.7)
    ax.axhline(25.0, color=RED, lw=0.9, ls=(0, (4, 3)))
    ax.set_ylabel(s.replace("SE01-", ""), rotation=0, ha="right", va="center", fontsize=8.5)
    ax.set_ylim(16, 47)
    ax.set_yticks([20, 30, 40])
    ax.tick_params(length=2)
axes[0].text(t1, 25.0, "  threshold 25.0", color=RED, fontsize=7.5, va="center")
axes[0].text(
    hourly[sensors[0]].index[int(len(hourly[sensors[0]]) * 0.75)],
    45.5,
    "evaluation holdout (walk-forward)",
    color=GREY,
    fontsize=7.5,
    ha="center",
    va="top",
)
wsub = weather.loc[t0:t1]
axes[4].bar(wsub.index, wsub["precip_mm"], width=1.2, color=GREEN, lw=0)
axes[4].set_ylabel("precip\n(mm/d)", rotation=0, ha="right", va="center", fontsize=8.5)
axes[4].tick_params(length=2)
fig.align_ylabels(axes)
fig.suptitle(
    "Soil moisture, four probes, Iron Horse Vineyards — 2026-01-22 to 2026-07-08 (hourly means)",
    fontsize=9.5,
    y=0.965,
)
save(fig, "fig1_data")

# ---------------------------------------------------------------- figure 2
# Rolling-origin (walk-forward) evaluation design.
fig, ax = plt.subplots(figsize=(7.2, 2.4))
n_folds, total = 5, 100.0
hold_start, fold_w = 50.0, 10.0
for k in range(n_folds):
    y = n_folds - k
    train_end = hold_start + k * fold_w
    ax.broken_barh([(0, train_end)], (y - 0.32, 0.64), color=GREEN, alpha=0.85)
    ax.broken_barh([(train_end, fold_w)], (y - 0.32, 0.64), color=BLUE)
    ax.text(-1.5, y, f"fold {k + 1}", ha="right", va="center", fontsize=8)
ax.axvline(hold_start, color=GREY, lw=0.8, ls=":")
ax.text(hold_start / 2, 5.85, "training (expanding)", color=GREEN, fontsize=8, ha="center")
ax.text(77, 5.85, "test (never seen at fit time)", color=BLUE, fontsize=8, ha="center")
ax.text(hold_start, 0.28, "holdout = most recent half", color=GREY, fontsize=7.5, ha="center")
ax.set_xlim(-14, 102)
ax.set_ylim(0, 6.4)
ax.set_xticks([])
ax.set_yticks([])
ax.grid(False)
for sp in ax.spines.values():
    sp.set_visible(False)
ax.annotate(
    "time",
    xy=(100, -0.02),
    xytext=(88, -0.02),
    fontsize=8,
    color=GREY,
    arrowprops=dict(arrowstyle="->", color=GREY, lw=0.8),
    va="center",
)
save(fig, "fig2_walkforward")

# ---------------------------------------------------------------- figure 3
# Point-forecast error vs horizon (SE01-LS-1), from the 2026-07-08 runs.
horizons = [6, 12, 24, 48]
mae = {
    "persistence": [0.105, 0.177, 0.283, 0.523],
    "seasonal-naive": [0.283, 0.283, 0.283, 0.523],
    "dry-down rule": [0.117, 0.196, 0.275, 0.538],
    "GBT (Δ + forecast)": [0.132, 0.155, 0.185, 1.125],
    "climatology": [5.419, 5.414, 5.408, 5.389],
}
styles = {
    "persistence": dict(color=GREEN, lw=2.0, marker="o", zorder=5),
    "seasonal-naive": dict(color=GOLD, lw=1.1, marker="s", ls="--"),
    "dry-down rule": dict(color=GREY, lw=1.1, marker="^", ls="--"),
    "GBT (Δ + forecast)": dict(color=BLUE, lw=1.1, marker="D", ls="--"),
    "climatology": dict(color=RED, lw=1.1, marker="v", ls=":"),
}
fig, ax = plt.subplots(figsize=(5.4, 3.4))
for name, vals in mae.items():
    ax.plot(horizons, vals, ms=4, label=name, **styles[name])
ax.set_yscale("log")
ax.set_xticks(horizons)
ax.set_xlabel("forecast horizon (hours)")
ax.set_ylabel("MAE (sensor units, log)")
ax.legend(fontsize=7.5, loc="center left", bbox_to_anchor=(1.01, 0.5))
ax.set_title("Point-forecast error by horizon — sensor SE01-LS-1 (n≈1,350/horizon)")
save(fig, "fig3_mae")

# ---------------------------------------------------------------- figure 4
# ARIMA skill vs persistence across sensors × horizons (the refutation).
skill = np.array(
    [
        [3.0, -1.8, 2.4, 2.1],  # LS-1
        [-6.1, -12.2, -18.0, -10.1],  # LS-2
        [1.7, 2.3, -3.0, -1.7],  # LS-3
        [3.8, -1.9, 2.0, 1.8],  # LS-4
    ]
)
fig, ax = plt.subplots(figsize=(5.2, 3.0))
im = ax.imshow(skill, cmap="RdYlGn", vmin=-18, vmax=18, aspect="auto")
ax.set_xticks(range(4), [f"{h} h" for h in horizons])
ax.set_yticks(range(4), [f"LS-{i}" for i in range(1, 5)])
for i in range(4):
    for j in range(4):
        v = skill[i, j]
        ax.text(
            j,
            i,
            f"{v:+.1f}%",
            ha="center",
            va="center",
            fontsize=8.5,
            color="white" if abs(v) > 9 else INK,
            fontweight="bold" if abs(v) > 9 else "normal",
        )
ax.set_title("ARIMA(2,1,2) skill vs persistence (positive = better)")
ax.grid(False)
cb = fig.colorbar(im, ax=ax, shrink=0.85)
cb.set_label("skill (%)", fontsize=8)
cb.ax.tick_params(labelsize=7.5)
save(fig, "fig4_arima")

# ---------------------------------------------------------------- figure 5
# The pooled-metric artifact: ridge+forecast @48h, per-fold skill.
folds = [0.549, -1.58, -1.63, 0.01, -0.18]
pooled = 0.15
fig, ax = plt.subplots(figsize=(5.0, 2.9))
colors = [GREEN if v > 0 else RED for v in folds]
ax.bar(range(1, 6), folds, color=colors, width=0.62, alpha=0.9)
ax.axhline(0, color=INK, lw=0.8)
ax.axhline(pooled, color=BLUE, lw=1.2, ls="--")
ax.text(5.55, pooled + 0.07, "pooled skill +15%", color=BLUE, fontsize=8, ha="right", va="bottom")
ax.text(1, 0.62, "one April\nrain episode", color=GREEN, fontsize=7.5, ha="center", va="bottom")
ax.set_xticks(range(1, 6), [f"fold {i}" for i in range(1, 6)])
ax.set_ylabel("skill vs persistence")
ax.set_ylim(-1.85, 1.1)
ax.set_xlim(0.4, 5.6)
ax.set_title("Why pooled metrics lie: ridge+forecast, 48 h, per fold")
save(fig, "fig5_folds")

print("all figures written to", OUT)


# ---------------------------------------------------------------- figure 0
# Proposal timeline (VINE_Proposal_1.pdf §5) with a "we are here" marker.
from datetime import datetime  # noqa: E402

UTC = None  # naive dates are fine for a Gantt chart
d = datetime
phases = [
    # (label, start, end, status)  — dates from the proposal timeline table
    ("Community bonding", d(2026, 5, 25), d(2026, 6, 14), "done"),
    ("D1 · Data pipeline", d(2026, 6, 8), d(2026, 6, 28), "done"),
    ("D2 · Irrigation models", d(2026, 6, 22), d(2026, 7, 12), "done"),
    ("D3 · Plant-health CV", d(2026, 7, 6), d(2026, 7, 26), "current"),
    ("D4+D5 · Harvest + eval report", d(2026, 7, 27), d(2026, 8, 9), "todo"),
    ("D6 · NRP deployment", d(2026, 8, 3), d(2026, 8, 16), "todo"),
    ("D7 · Docs + polish", d(2026, 8, 10), d(2026, 8, 24), "todo"),
]
status_color = {"done": GREEN, "current": BLUE, "todo": "#c3ccc1"}
today = d(2026, 7, 9)
midterm = d(2026, 7, 12)

fig, ax = plt.subplots(figsize=(7.6, 3.3))
for i, (label, start, end, status) in enumerate(phases):
    y = len(phases) - i
    ax.barh(
        y,
        end - start,
        left=start,
        height=0.55,
        color=status_color[status],
        alpha=0.95 if status != "todo" else 0.8,
    )
    ax.text(
        start,
        y + 0.42,
        label,
        fontsize=7.8,
        va="bottom",
        color=INK,
        fontweight="bold" if status == "current" else "normal",
    )
ax.axvline(today, color=RED, lw=1.4)
ax.text(
    today,
    len(phases) + 1.15,
    " WE ARE HERE (Jul 9)",
    color=RED,
    fontsize=8.5,
    fontweight="bold",
    va="bottom",
)
ax.axvline(midterm, color=GREY, lw=1.0, ls=":")
ax.text(
    midterm,
    0.42,
    ' midterm eval — proposal target:\n "D1, D2 complete. D3 in progress"',
    color=GREY,
    fontsize=7.2,
    va="bottom",
)
ax.set_ylim(0.3, len(phases) + 1.8)
ax.set_yticks([])
ax.grid(axis="y", visible=False)
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (GREEN, BLUE, "#c3ccc1")]
ax.legend(
    handles,
    ["done", "in progress", "upcoming"],
    loc="upper right",
    fontsize=7.5,
    ncols=3,
    bbox_to_anchor=(1.0, 1.14),
)
import matplotlib.dates as mdates  # noqa: E402

ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=2))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.tick_params(axis="x", labelsize=7.5)
save(fig, "fig0_timeline")
