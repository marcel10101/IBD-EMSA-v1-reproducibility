from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

from figure3_config import COLORS, DATA_PROCESSED_DIR, FIGURE3_ROOT, LOG_DIR, TIFF_DPI, ensure_directories
from figure3_plot_utils import add_panel_letter, save_panel, set_style


SCRIPT_DIR = Path(__file__).resolve().parent
CHARTS_ROOT = FIGURE3_ROOT.parent
DATA_ROOT = CHARTS_ROOT.parent
WORKSPACE_ROOT = DATA_ROOT.parent
SCORE_SOURCE = DATA_ROOT / "六维评分" / "panel_E_tier1_six_dimension_scores_recalculated.csv"
PANEL_DIR = FIGURE3_ROOT / "panels" / "E"
AUDIT_MD = PANEL_DIR / "panel_E_tier1_six_dimension_radar_audit.md"
LABEL_MAP_CSV = DATA_PROCESSED_DIR / "panel_E_tier1_feature_label_map.csv"
SCORES_LONG_CSV = DATA_PROCESSED_DIR / "panel_E_tier1_six_dimension_radar_scores.csv"
VALIDATION_JSON = LOG_DIR / "panel_E_tier1_six_dimension_radar_validation.json"
BASENAME = "panel_E_tier1_six_dimension_radar"

DIMENSIONS = [
    ("Evidence\nfrequency", "evidence_frequency_score", 20.0, "Evidence frequency"),
    ("Direction\nconsistency", "direction_score", 20.0, "Direction consistency"),
    ("Effect\nstrength", "effect_strength_score", 15.0, "Effect strength"),
    ("Disease-process\ncoverage", "disease_process_score", 15.0, "Disease-process coverage"),
    ("Mechanistic\nrelevance", "mechanism_score", 15.0, "Mechanistic relevance"),
    ("Model\nsupport", "model_support_score", 15.0, "Model support"),
]


def panel_paths() -> dict[str, Path]:
    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "svg": PANEL_DIR / f"{BASENAME}.svg",
        "pdf": PANEL_DIR / f"{BASENAME}.pdf",
        "tiff": PANEL_DIR / f"{BASENAME}.tiff",
        "png": PANEL_DIR / f"{BASENAME}.png",
        "metadata": LOG_DIR / "panel_E_tier1_six_dimension_radar_layout_metadata.json",
    }


def add_result(results: list[dict[str, Any]], check: str, passed: bool, detail: str) -> None:
    results.append({"check": check, "passed": bool(passed), "detail": detail})


def svg_text(path: Path) -> str:
    root = ET.parse(path).getroot()
    parts: list[str] = []
    for elem in root.iter():
        if elem.tag.endswith("text") or elem.tag.endswith("tspan"):
            if elem.text:
                parts.append(elem.text)
    return " ".join(parts)


def short_label(label: str, used: set[str]) -> tuple[str, bool]:
    clean = " ".join(str(label).split())
    if "SGB4262" in clean or "Ruminococcus_bicirculans" in clean:
        clean = "Ruminococcus bicirculans / SGB4262"
    elif "SGB15286" in clean or "Subdoligranulum" in clean:
        clean = "Subdoligranulum sp. / SGB15286"
    elif "SGB15260" in clean or "GGB9715" in clean:
        clean = "Ruminococcaceae-related SGB15260"
    clean = clean.replace("metabolite__", "").replace("microbe__", "")
    clean = clean.replace("metabolome::", "").replace("microbiome::", "")
    clean = clean.replace("_", " ")
    if len(clean) <= 34:
        candidate = clean
    elif " / SGB" in clean:
        candidate = clean.split(" / ")[-1]
    elif clean.startswith("p-Hydroxy"):
        candidate = "p-Hydroxyphenylacetic acid"
    else:
        words = clean.split()
        candidate = " ".join(words[:3])
    if candidate in used:
        base = candidate
        idx = 2
        while f"{base} ({idx})" in used:
            idx += 1
        candidate = f"{base} ({idx})"
    used.add(candidate)
    return candidate, candidate != clean


def load_and_validate_source() -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    add_result(results, "source_exists", SCORE_SOURCE.exists(), str(SCORE_SOURCE))
    if not SCORE_SOURCE.exists():
        return pd.DataFrame(), results
    frame = pd.read_csv(SCORE_SOURCE, dtype=object).fillna("")
    add_result(results, "tier_i_row_count_15", len(frame) == 15, f"rows={len(frame)}")
    counts = frame["omics_layer"].value_counts().to_dict() if "omics_layer" in frame else {}
    add_result(results, "omics_split_5_10", counts == {"metabolome": 10, "microbiome": 5}, str(counts))
    required = ["feature_id", "feature_label", "omics_layer"] + [column for _, column, _, _ in DIMENSIONS]
    missing = [column for column in required if column not in frame.columns]
    add_result(results, "required_columns_present", not missing, f"missing={missing}")
    if missing:
        return frame, results
    for _, column, cap, label in DIMENSIONS:
        values = pd.to_numeric(frame[column], errors="coerce")
        add_result(results, f"{column}_numeric", values.notna().all(), f"{label}: non-null={int(values.notna().sum())}")
        mapped = values / cap * 6.0
        add_result(results, f"{column}_mapped_0_6", mapped.between(0, 6).all(), f"min={mapped.min()} max={mapped.max()} cap={cap}")
    return frame, results


def prepare_scores(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    used_by_omics: dict[str, set[str]] = {"microbiome": set(), "metabolome": set()}
    label_map: list[dict[str, Any]] = []
    frame = frame.copy()
    frame["plot_label"] = ""
    for idx, row in frame.iterrows():
        label = str(row["feature_label"])
        if frame["feature_label"].astype(str).eq(label).sum() > 1:
            label = f"{label} ({row['omics_layer']})"
        plotted, shortened = short_label(label, used_by_omics[str(row["omics_layer"])])
        frame.loc[idx, "plot_label"] = plotted
        label_map.append(
            {
                "feature_id": row["feature_id"],
                "omics_layer": row["omics_layer"],
                "feature_label": row["feature_label"],
                "plot_label": plotted,
                "label_shortened": shortened,
            }
        )
    for _, row in frame.iterrows():
        for display, column, cap, full_label in DIMENSIONS:
            raw = float(pd.to_numeric(pd.Series([row[column]]), errors="raise").iloc[0])
            plotted = max(0.0, min(6.0, raw / cap * 6.0))
            rows.append(
                {
                    "feature_id": row["feature_id"],
                    "omics_layer": row["omics_layer"],
                    "feature_label": row["feature_label"],
                    "plot_label": row["plot_label"],
                    "dimension": full_label,
                    "source_column": column,
                    "raw_score": raw,
                    "dimension_max": cap,
                    "plotted_value_0_6": plotted,
                    "normalization_formula": "score / dimension_max * 6",
                    "score_source_file": str(SCORE_SOURCE),
                }
            )
    long = pd.DataFrame(rows)
    label_map_frame = pd.DataFrame(label_map)
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    long.to_csv(SCORES_LONG_CSV, index=False, encoding="utf-8-sig")
    if label_map_frame["label_shortened"].any() or label_map_frame["feature_label"].duplicated().any():
        label_map_frame.to_csv(LABEL_MAP_CSV, index=False, encoding="utf-8-sig")
    return long, label_map_frame


def draw_radar(long: pd.DataFrame) -> None:
    set_style()
    paths = panel_paths()
    fig = plt.figure(figsize=(175 / 25.4, 88 / 25.4), dpi=TIFF_DPI)
    fig.patch.set_facecolor("white")
    add_panel_letter(fig, "E")
    fig.text(0.25, 0.940, "Microbiome Tier I features (n = 5)", ha="center", va="top", fontsize=7.8, fontweight="bold")
    fig.text(0.73, 0.940, "Metabolome Tier I features (n = 10)", ha="center", va="top", fontsize=7.8, fontweight="bold")
    axes = [
        fig.add_axes([0.08, 0.29, 0.34, 0.54], projection="polar"),
        fig.add_axes([0.56, 0.29, 0.34, 0.54], projection="polar"),
    ]
    groups = [
        ("microbiome", "Microbiome Tier I features (n = 5)", plt.cm.PuBuGn(np.linspace(0.52, 0.88, 5))),
        ("metabolome", "Metabolome Tier I features (n = 10)", plt.cm.YlOrRd(np.linspace(0.42, 0.82, 10))),
    ]
    labels = [display for display, _, _, _ in DIMENSIONS]
    theta = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
    theta_closed = np.r_[theta, theta[0]]

    for ax, (omics, title, colors) in zip(axes, groups):
        subset = long[long["omics_layer"].eq(omics)]
        feature_order = subset[["feature_id", "plot_label"]].drop_duplicates().sort_values("plot_label")
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_ylim(0, 6)
        ax.set_yticks([0, 1, 2, 3, 4, 5, 6])
        ax.set_yticklabels(["0", "1", "2", "3", "4", "5", "6"], fontsize=5.4, color=COLORS["grey"])
        ax.set_xticks(theta)
        ax.set_xticklabels(labels, fontsize=6.0)
        ax.grid(color="#D0D5DA", lw=0.45)
        ax.spines["polar"].set_color("#B8BFC6")
        ax.spines["polar"].set_linewidth(0.6)
        handles = []
        for color, (_, feature) in zip(colors, feature_order.iterrows()):
            values = subset[subset["feature_id"].eq(feature["feature_id"])].set_index("dimension")
            ordered = [float(values.loc[full_label, "plotted_value_0_6"]) for _, _, _, full_label in DIMENSIONS]
            closed = np.r_[ordered, ordered[0]]
            (line,) = ax.plot(theta_closed, closed, color=color, lw=0.9, marker="o", ms=2.0, alpha=0.92)
            ax.fill(theta_closed, closed, color=color, alpha=0.075)
            handles.append(line)
        ncol = 1 if omics == "microbiome" else 2
        anchor = (0.5, -0.13 if omics == "microbiome" else -0.16)
        ax.legend(
            handles,
            feature_order["plot_label"].tolist(),
            loc="upper center",
            bbox_to_anchor=anchor,
            ncol=ncol,
            fontsize=5.1,
            frameon=False,
            handlelength=1.4,
            columnspacing=0.8,
            handletextpad=0.35,
        )
    save_panel(fig, paths)


def validate_outputs(results: list[dict[str, Any]]) -> None:
    paths = panel_paths()
    for key in ["svg", "pdf", "tiff", "png"]:
        add_result(results, f"{key}_exists", paths[key].exists(), str(paths[key]))
    if paths["svg"].exists():
        text = svg_text(paths["svg"])
        add_result(results, "svg_editable_text", len(text.strip()) > 0, f"{len(text)} text chars")
        banned = ["missing", "blocked", "unavailable", "insufficient", "fail-fast"]
        hits = [word for word in banned if word in text.lower()]
        add_result(results, "visible_text_has_no_banned_status_words", not hits, f"hits={hits}")
    if paths["tiff"].exists():
        with Image.open(paths["tiff"]) as image:
            add_result(results, "tiff_rgb", image.mode == "RGB", image.mode)
            dpi = image.info.get("dpi", (0, 0))
            add_result(results, "tiff_600dpi", all(abs(float(value) - TIFF_DPI) < 1 for value in dpi), str(dpi))
            add_result(results, "tiff_lzw", image.tag_v2.get(259) == 5, f"tag={image.tag_v2.get(259)}")


def write_audit(results: list[dict[str, Any]], label_map: pd.DataFrame | None, long: pd.DataFrame | None) -> None:
    all_passed = all(item["passed"] for item in results)
    lines = [
        "# Panel E Tier I Six-Dimension Radar Audit",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Status: {'success' if all_passed else 'failed'}",
        f"- Source file used: `{SCORE_SOURCE}`",
        "- Score columns used: `evidence_frequency_score`, `direction_score`, `effect_strength_score`, `disease_process_score`, `mechanism_score`, `model_support_score`.",
        "- Normalization formula: `plotted_value = score / dimension_max * 6`.",
        "- Dimension maxima: evidence frequency 20; direction 20; effect 15; disease process 15; mechanism 15; model support 15.",
        "- Confirmation: no generative AI was used.",
        "",
        "## Feature Counts",
    ]
    if long is not None and not long.empty:
        counts = long[["feature_id", "omics_layer"]].drop_duplicates()["omics_layer"].value_counts().to_dict()
        lines.append(f"- Microbiome Tier I: {counts.get('microbiome', 0)}")
        lines.append(f"- Metabolome Tier I: {counts.get('metabolome', 0)}")
        lines.append("")
        lines.append("## Feature Labels")
        for _, row in long[["feature_id", "omics_layer", "feature_label", "plot_label"]].drop_duplicates().sort_values(["omics_layer", "plot_label"]).iterrows():
            lines.append(f"- `{row['omics_layer']}`: {row['plot_label']} (`{row['feature_id']}`)")
    if label_map is not None and not label_map.empty:
        lines.extend(["", "## Label Shortening Map"])
        for _, row in label_map.iterrows():
            lines.append(f"- {row['feature_label']} -> {row['plot_label']} (shortened={row['label_shortened']})")
    lines.extend(["", "## Output Files"])
    for key, path in panel_paths().items():
        if key != "metadata":
            lines.append(f"- `{path}`")
    lines.extend(["", "## Validation Results", "", "| Check | Status | Detail |", "|---|---:|---|"])
    for item in results:
        detail = str(item["detail"]).replace("|", "\\|")
        lines.append(f"| {item['check']} | {'PASS' if item['passed'] else 'FAIL'} | {detail} |")
    AUDIT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    VALIDATION_JSON.write_text(json.dumps({"all_passed": all_passed, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")


def build_panel_e() -> dict[str, Any]:
    ensure_directories()
    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    frame, results = load_and_validate_source()
    long = None
    label_map = None
    if all(item["passed"] for item in results):
        long, label_map = prepare_scores(frame)
        draw_radar(long)
        validate_outputs(results)
    write_audit(results, label_map, long)
    return {
        "panel": "E",
        "status": "success" if all(item["passed"] for item in results) else "failed",
        "outputs": [str(path) for key, path in panel_paths().items() if key != "metadata" and path.exists()],
        "audit": str(AUDIT_MD),
        "validation": results,
        "source": str(SCORE_SOURCE),
    }


if __name__ == "__main__":
    payload = build_panel_e()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
