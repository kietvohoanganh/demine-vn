"""Figures for the strict-real pipeline.

These figures intentionally avoid UXO-ground-truth claims.  They visualise
observed/derived real-data inputs and the relative survey-priority score only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence
import textwrap

import numpy as np
import pandas as pd

INK = "#1C3557"
BLUE = "#4C7FB0"
MINT = "#5FA383"
BLUSH = "#C9705C"
CREAM = "#DFC58A"
GRID = "#E4ECF4"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.dpi": 130,
        "savefig.dpi": 150,
        "font.size": 9.5,
        "axes.edgecolor": "#9DBCDA",
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })
    return plt


def _save(fig, path: Path, *, bottom: float = 0.03, right: float = 0.98, top: float = 0.95):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0.02, bottom, right, top))
    fig.savefig(path, bbox_inches="tight", pad_inches=0.16)


def _grid_array(df: pd.DataFrame, column: str, shape: tuple[int, int]) -> np.ndarray:
    arr = np.full(shape[0] * shape[1], np.nan, dtype=float)
    idx = df["chi_so_o_luoi"].to_numpy(int)
    valid = (idx >= 0) & (idx < arr.size)
    arr[idx[valid]] = df.loc[valid, column].to_numpy(float)
    return arr.reshape(shape)


def _priority_concentration(scores: Sequence[float]):
    s = np.asarray(scores, dtype=float)
    s = np.where(np.isfinite(s) & (s > 0), s, 0.0)
    order = np.sort(s)[::-1]
    n = len(order)
    area = np.arange(1, n + 1) / max(n, 1)
    total = order.sum()
    cumulative = np.cumsum(order) / total if total > 0 else np.zeros_like(order)
    return area, cumulative


def fig_priority_concentration(df: pd.DataFrame, path: Path):
    plt = _plt()
    area, cumulative = _priority_concentration(df["chi_so_uu_tien"])
    fig, ax = plt.subplots(figsize=(6.7, 5.0))
    ax.plot(area * 100, cumulative * 100, color=INK, linewidth=2.2,
            label="Xếp theo chỉ số ưu tiên")
    ax.plot([0, 100], [0, 100], color=BLUSH, linestyle="--", linewidth=1.5,
            label="Phân bố đều")
    i20 = min(len(area) - 1, max(0, int(np.ceil(.20 * len(area))) - 1))
    y20 = cumulative[i20] * 100 if len(cumulative) else 0
    ax.axvline(20, color=CREAM, linewidth=1.2, linestyle=":")
    ax.scatter([20], [y20], s=48, color=MINT, edgecolor="white", linewidth=.8, zorder=5)
    ax.annotate(
        f"Top 20% diện tích\nbao phủ {y20:.1f}% tổng điểm ưu tiên",
        xy=(20, y20), xytext=(38, max(12, y20 - 24)),
        arrowprops=dict(arrowstyle="->", color=MINT, linewidth=1.2),
        bbox=dict(boxstyle="round,pad=.3", facecolor="white", edgecolor="#DDE6EF", alpha=.94),
    )
    ax.set(xlim=(0, 100), ylim=(0, 100),
           xlabel="Tỉ lệ diện tích ưu tiên (%)",
           ylabel="Tỉ lệ tổng chỉ số ưu tiên được bao phủ (%)",
           title="Mức tập trung của bằng chứng trong vùng ưu tiên")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=8.5)
    _save(fig, path, bottom=.14)
    plt.close(fig)


def fig_priority_map(df: pd.DataFrame, grid_shape: tuple[int, int], path: Path, top_markers: int = 20):
    plt = _plt()
    arr = _grid_array(df, "chi_so_uu_tien", grid_shape)
    vmax = float(np.nanquantile(arr, .995)) if np.isfinite(arr).any() else 1.0
    fig, ax = plt.subplots(figsize=(8.5, 6.0))
    im = ax.imshow(arr, origin="lower", cmap="YlOrRd", vmin=0, vmax=max(vmax, 1e-9), interpolation="nearest")

    top = df.nsmallest(min(top_markers, len(df)), "thu_tu_uu_tien")
    idx = top["chi_so_o_luoi"].to_numpy(int)
    x = idx % grid_shape[1]
    y = idx // grid_shape[1]
    # Strong contrast: white halo + cyan fill + navy edge.
    ax.scatter(x, y, s=90, facecolor="white", edgecolor="white", linewidth=2.2, zorder=5)
    ax.scatter(x, y, s=52, facecolor="#53D8FB", edgecolor="#08306B", linewidth=1.3, zorder=6,
               label=f"Top {len(top)} khu vực")
    # Keep boundary markers fully visible without allowing them to collide with titles.
    ax.set_xlim(-2.5, grid_shape[1] + 1.5)
    ax.set_ylim(-2.5, grid_shape[0] + 1.5)

    cb = fig.colorbar(im, ax=ax, fraction=.035, pad=.025)
    cb.set_label("Chỉ số ưu tiên tương đối (0–1)")
    ax.set_title("Bản đồ ưu tiên khảo sát/rà phá")
    ax.set_xlabel("Ô lưới theo hướng đông")
    ax.set_ylabel("Ô lưới theo hướng bắc")
    ax.grid(False)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.105), fontsize=8.5)
    fig.text(.5, .012,
             "Marker là tâm ô phân tích ưu tiên — không phải vị trí UXO đã được xác nhận.",
             ha="center", fontsize=8.4, color=INK)
    _save(fig, path, bottom=.12, right=.98)
    plt.close(fig)


def fig_source_panels(df: pd.DataFrame, grid_shape: tuple[int, int], path: Path):
    plt = _plt()
    layers = [
        ("tai_trong_bom_ghi_nhan_tan", "THOR thật\nTải trọng ghi nhận", "Blues"),
        ("so_ho_bom_phat_hien", "KH-9 thật\nHố bom phát hiện", "Greens"),
        ("chi_so_uu_tien", "Kết quả tổng hợp\nChỉ số ưu tiên", "YlOrRd"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(11.8, 4.2))
    for ax, (col, title, cmap) in zip(axes, layers):
        arr = _grid_array(df, col, grid_shape)
        vmax = float(np.nanquantile(arr, .995)) if np.isfinite(arr).any() else 1.0
        ax.imshow(arr, origin="lower", cmap=cmap, vmin=0, vmax=max(vmax, 1e-9), interpolation="nearest")
        ax.set_title(title, fontsize=9.4, pad=9)
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    fig.suptitle("Ba lớp thông tin trên cùng vùng nghiên cứu", fontsize=12, y=.985)
    fig.text(.5, .025,
             "Hai nguồn quan sát thật (THOR, KH-9) được tổng hợp thành chỉ số ưu tiên tương đối.",
             ha="center", fontsize=8.5, color=INK)
    _save(fig, path, bottom=.07, top=.88)
    plt.close(fig)


def fig_priority_distribution(df: pd.DataFrame, path: Path):
    plt = _plt()
    order = ["Rất cao", "Cao", "Trung bình", "Thấp", "Rất thấp"]
    counts = df["muc_uu_tien"].value_counts()
    existing = [x for x in order if x in counts.index]
    # Include any unexpected label rather than silently discarding it.
    existing += [x for x in counts.index if x not in existing]
    vals = [int(counts.get(x, 0)) for x in existing]
    fig, ax = plt.subplots(figsize=(6.8, 4.5))
    bars = ax.bar(existing, vals, color=BLUE)
    total = max(sum(vals), 1)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, b.get_height(), f"{v:,}\n({v/total*100:.1f}%)",
                ha="center", va="bottom", fontsize=8.2)
    ax.set_title("Phân bố mức ưu tiên trong vùng nghiên cứu")
    ax.set_ylabel("Số ô lưới")
    ax.set_xlabel("Mức ưu tiên")
    ax.margins(y=.16)
    _save(fig, path)
    plt.close(fig)


def fig_feature_weights(weights: Mapping[str, float], path: Path):
    plt = _plt()
    items = sorted(((str(k), float(v)) for k, v in weights.items()), key=lambda kv: kv[1])
    names = [textwrap.fill(k.replace("_", " "), 30) for k, _ in items]
    vals = [v for _, v in items]
    fig_h = max(4.6, .36 * len(items) + 1.8)
    fig, ax = plt.subplots(figsize=(7.3, fig_h))
    bars = ax.barh(names, vals, color=BLUE)
    for b, v in zip(bars, vals):
        ax.text(v + max(vals or [1])*.01, b.get_y()+b.get_height()/2, f"{v:.3f}", va="center", fontsize=8)
    ax.set_title("Trọng số minh bạch của chỉ số ưu tiên")
    ax.set_xlabel("Trọng số")
    ax.set_ylabel("")
    ax.margins(x=.12)
    _save(fig, path, right=.97)
    plt.close(fig)


def fig_top_cells(df: pd.DataFrame, path: Path, n: int = 12):
    plt = _plt()
    d = df.nsmallest(min(n, len(df)), "thu_tu_uu_tien").sort_values("thu_tu_uu_tien", ascending=False)
    labels = [f"#{int(v)}" for v in d["thu_tu_uu_tien"]]
    vals = d["chi_so_uu_tien"].to_numpy(float)
    fig, ax = plt.subplots(figsize=(7.0, 4.8))
    bars = ax.barh(labels, vals, color=BLUE)
    lo = max(0.0, float(vals.min()) - .03) if len(vals) else 0
    ax.set_xlim(lo, 1.01)
    for b, v in zip(bars, vals):
        ax.text(v + .003, b.get_y()+b.get_height()/2, f"{v:.3f}", va="center", fontsize=8.1)
    ax.set_title("Các ô có thứ tự ưu tiên cao nhất")
    ax.set_xlabel("Chỉ số ưu tiên tương đối (0–1) — trục thu phóng")
    ax.set_ylabel("Thứ hạng")
    _save(fig, path)
    plt.close(fig)


def make_strict_real_figures(df: pd.DataFrame, grid_shape: tuple[int, int], weights: Mapping[str, float], out_dir: Path):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("01_muc_tap_trung_uu_tien.png", lambda p: fig_priority_concentration(df, p)),
        ("02_ban_do_uu_tien.png", lambda p: fig_priority_map(df, grid_shape, p)),
        ("03_ba_lop_du_lieu_that.png", lambda p: fig_source_panels(df, grid_shape, p)),
        ("04_phan_bo_muc_uu_tien.png", lambda p: fig_priority_distribution(df, p)),
        ("05_trong_so_chi_so.png", lambda p: fig_feature_weights(weights, p)),
        ("06_top_o_uu_tien.png", lambda p: fig_top_cells(df, p)),
    ]
    made = []
    for name, fn in jobs:
        path = out_dir / name
        fn(path)
        made.append(path)
    return made
