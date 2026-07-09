"""Fig 6 (holdout alert demo, real data) + datasheet/split statistics for the report."""

import base64
import os
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")

OUT = Path(os.environ.get("OUT", "figs"))
DATA = Path("data/raw")
GREEN, BLUE, RED, GREY, INK = "#2e7a4c", "#31699c", "#b34a2e", "#5b6a5f", "#1b231d"

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 9,
        "axes.titlesize": 9.5,
        "axes.edgecolor": GREY,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#dfe6dc",
        "grid.linewidth": 0.6,
        "text.color": INK,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "legend.frameon": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.dpi": 170,
        "savefig.bbox": "tight",
    }
)

sensors = ["SE01-LS-1", "SE01-LS-2", "SE01-LS-3", "SE01-LS-4"]

# ---------------- datasheet stats ----------------
print(
    f"{'sensor':<12} {'raw rows':>9} {'start':>12} {'end':>12} {'hourly n':>9} {'gap %':>6} {'mean':>6} {'min':>6} {'max':>6} {'<25 %':>6}"
)
hourly = {}
for s in sensors:
    df = pd.read_parquet(DATA / "sensors" / f"{s}.parquet")
    y = df["soil_water"].resample("1h").mean()
    hourly[s] = y
    gaps = y.isna().mean() * 100
    print(
        f"{s:<12} {len(df):>9,} {str(y.index[0].date()):>12} {str(y.index[-1].date()):>12}"
        f" {len(y):>9,} {gaps:>5.1f}% {y.mean():>6.2f} {y.min():>6.2f} {y.max():>6.2f}"
        f" {(y < 25).mean() * 100:>5.1f}%"
    )

# ---------------- fold boundaries (LS-1, expanding splits over most recent half, 5 folds) ----
y = hourly["SE01-LS-1"]
n = len(y)
hold_start = n // 2
fold_len = (n - hold_start) // 5
print("\nLS-1 walk-forward fold boundaries (hourly grid):")
print(f"  series: {y.index[0]} .. {y.index[-1]}  (n={n:,} hourly steps)")
print(f"  holdout starts: {y.index[hold_start]}")
for k in range(5):
    a, b = hold_start + k * fold_len, hold_start + (k + 1) * fold_len
    b = min(b, n) - 1
    print(
        f"  fold {k + 1}: train n={a:,} (.. {y.index[a - 1].date()}), test {y.index[a].date()} .. {y.index[b].date()} (n={b - a + 1:,})"
    )

# ---------------- figure 6: real holdout window, persistence forecast + alerts ----
s = "SE01-LS-2"
h = 24
yy = hourly[s].loc["2026-04-12":]
fc = yy.shift(h)  # persistence forecast FOR time t, made at t-24h
alert = fc < 25.0

fig, ax = plt.subplots(figsize=(7.4, 3.0))
ax.fill_between(
    yy.index, 16, 48, where=alert.fillna(False), color=RED, alpha=0.08, lw=0, step="mid"
)
ax.plot(yy.index, yy.values, color=BLUE, lw=0.9, label="observed soil moisture")
ax.plot(
    fc.index, fc.values, color=GREEN, lw=1.0, ls="--", label=f"persistence forecast ({h} h ahead)"
)
ax.axhline(25.0, color=RED, lw=0.9, ls=(0, (4, 3)), label="irrigation threshold (25.0)")
ax.set_ylim(16, 33)
ax.set_ylabel("soil moisture (sensor units)")
ax.legend(fontsize=7.5, loc="upper right", ncols=1)
ax.set_title(f"Holdout period, sensor {s}: 24 h persistence forecast and fired alerts (shaded)")
p = OUT / "fig6_alerts.png"
fig.savefig(p)
(OUT / "fig6_alerts.b64").write_text(base64.b64encode(p.read_bytes()).decode())
print(
    f"\nfig6_alerts: {p.stat().st_size / 1024:.0f} KB; alert rows {int(alert.sum()):,}/{alert.notna().sum():,}"
)
