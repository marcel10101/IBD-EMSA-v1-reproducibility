from __future__ import annotations

import json
from datetime import datetime

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import ListedColormap

from figure4_config import COLORS, LOG_DIR, MODULE_COLORS, MODULE_ORDER, PANEL_STATUS, ensure_directories
from figure4_data_utils import build_master_table, load_master_table, module_subset, panel_output_paths, write_panel_trace, write_source_hash_snapshot
from figure4_plot_utils import add_panel_letter, new_panel, save_panel
from build_panel_A_network import panel_a_network


def short_name(name: str, max_len: int = 32) -> str:
    if len(name) <= max_len:
        return name
    return name[: max_len - 1] + "..."


def evidence_matrix(master: pd.DataFrame) -> pd.DataFrame:
    columns = [
        ("IBD vs Reference", "diagnosis_evidence"),
        ("CD vs Reference", None),
        ("UC vs Reference", None),
        ("Active vs Remission", "active_evidence"),
        ("Relapse-related", "relapse_evidence"),
        ("Post-treatment / state shift", "post_treatment_evidence"),
    ]
    rows = []
    for _, row in master.iterrows():
        item = {"standardized_feature_name": row["standardized_feature_name"], "module": row["assigned_figure4_module"], "omics_layer": row["omics_layer"]}
        for label, field in columns:
            if field is None:
                item[label] = 0
                item[f"{label} status"] = "not available"
            else:
                status = row.get(field, "not available")
                if status == "direct comparison support":
                    item[label] = int(float(row.get("evidence_strength_score", 0) or 0))
                elif status == "limited anchor support" or status == "limited evidence":
                    item[label] = 0.5
                else:
                    item[label] = 0
                item[f"{label} status"] = status
        rows.append(item)
    frame = pd.DataFrame(rows)
    frame.to_csv(panel_output_paths("A")["trace"].parent / "panel_A_evidence_matrix.csv", index=False, encoding="utf-8-sig")
    return frame


def panel_a() -> None:
    panel_a_network()


def panel_b() -> None:
    master = load_master_table()
    fig, ax = new_panel(118, 92)
    add_panel_letter(fig, "B")
    ax.axis("off")
    ax.text(0.02, 0.96, "Tier I features grouped by omics and module", transform=ax.transAxes, fontsize=8.5, fontweight="bold", va="top")
    y = 0.88
    for _, row in master.iterrows():
        module = row["assigned_figure4_module"]
        color = MODULE_COLORS.get(module, COLORS["grey_line"])
        ax.add_patch(patches.Rectangle((0.02, y - 0.025), 0.025, 0.022, transform=ax.transAxes, color=COLORS["mint"] if row["omics_layer"] == "microbiome" else COLORS["orange"]))
        ax.add_patch(patches.Rectangle((0.055, y - 0.025), 0.025, 0.022, transform=ax.transAxes, color=color))
        ax.text(0.09, y - 0.014, short_name(row["standardized_feature_name"], 56), transform=ax.transAxes, fontsize=6.2, va="center")
        ax.text(0.70, y - 0.014, row["omics_layer"], transform=ax.transAxes, fontsize=5.8, va="center", color=COLORS["grey"])
        ax.text(0.83, y - 0.014, "?" if row["direction"] == "?" else row["direction"], transform=ax.transAxes, fontsize=6.2, va="center", color=COLORS["grey"])
        y -= 0.052
    ax.text(0.02, 0.025, "Left strip: omics; second strip: functional module; ?: insufficient direction evidence.", transform=ax.transAxes, fontsize=6.2, color=COLORS["grey"])
    write_panel_trace(
        "B",
        [{"displayed_element": "Tier I feature list", "displayed_value": len(master), "source_column": "standardized_feature_name; omics_layer; assigned_figure4_module", "source_row_or_rule": "figure4_tier1_master_table.csv"}],
    )
    save_panel(fig, panel_output_paths("B"))


def panel_c() -> None:
    master = load_master_table()
    resolved = master[master["assignment_status"] == "resolved"].copy()
    fig, ax = new_panel(128, 92)
    add_panel_letter(fig, "C")
    ax.axis("off")
    module_lanes = {
        MODULE_ORDER[0]: (0.15, "SCFAs /\nbutyrate taxa"),
        MODULE_ORDER[1]: (0.38, "Bile\nacids"),
        MODULE_ORDER[2]: (0.61, "Amino acids /\naromatic amino acids"),
        MODULE_ORDER[3]: (0.84, "Oxidative-stress\nlipids"),
    }
    ax.text(0.5, 0.96, "Functional module membership network", transform=ax.transAxes, ha="center", fontsize=8.5, fontweight="bold")
    for module in MODULE_ORDER:
        subset = resolved[resolved["assigned_figure4_module"] == module].reset_index(drop=True)
        mx, module_label = module_lanes[module]
        ax.add_patch(
            patches.FancyBboxPatch(
                (mx - 0.085, 0.73),
                0.17,
                0.11,
                boxstyle="round,pad=0.006,rounding_size=0.018",
                transform=ax.transAxes,
                facecolor=MODULE_COLORS[module],
                edgecolor=COLORS["black"],
                lw=0.6,
            )
        )
        ax.text(mx, 0.785, module_label, transform=ax.transAxes, ha="center", va="center", fontsize=5.2, fontweight="bold", linespacing=0.95)
        ax.plot([mx, mx], [0.72, 0.26], transform=ax.transAxes, color=COLORS["grey_line"], lw=0.7, zorder=0)
        for idx, (_, row) in enumerate(subset.iterrows()):
            fy = 0.64 - idx * 0.075
            ax.plot([mx, mx], [fy + 0.028, fy + 0.022], transform=ax.transAxes, color=COLORS["grey_line"], lw=0.7, zorder=0)
            shape = patches.FancyBboxPatch(
                (mx - 0.087, fy - 0.026),
                0.174,
                0.052,
                boxstyle="round,pad=0.004,rounding_size=0.01",
                transform=ax.transAxes,
                facecolor="white",
                edgecolor=MODULE_COLORS[module],
                lw=0.8,
            )
            ax.add_patch(shape)
            ax.text(mx, fy, short_name(row["standardized_feature_name"], 22), transform=ax.transAxes, ha="center", va="center", fontsize=4.7)
    ax.text(0.5, 0.04, "Edges show project-defined module membership only; no statistical strength is encoded.", transform=ax.transAxes, ha="center", fontsize=6.2, color=COLORS["grey"])
    write_panel_trace(
        "C",
        [{"displayed_element": "module membership edges", "displayed_value": len(resolved), "source_column": "assigned_figure4_module; assignment_method", "source_row_or_rule": "Only resolved assignments are plotted; edge width has no statistical meaning."}],
    )
    save_panel(fig, panel_output_paths("C"))


def module_panel(panel: str, title: str, module: str, mechanism: str) -> None:
    master = load_master_table()
    subset = module_subset(master, module)
    fig, ax = new_panel(96, 62)
    add_panel_letter(fig, panel)
    ax.axis("off")
    color = MODULE_COLORS[module]
    ax.text(0.02, 0.94, title, transform=ax.transAxes, fontsize=8.5, fontweight="bold", va="top", color=COLORS["blue_dark"])
    ax.text(0.02, 0.80, mechanism, transform=ax.transAxes, fontsize=7, color=COLORS["grey"])
    y = 0.62
    for _, row in subset.iterrows():
        ax.add_patch(patches.FancyBboxPatch((0.04, y - 0.035), 0.64, 0.055, boxstyle="round,pad=0.006,rounding_size=0.012", transform=ax.transAxes, facecolor="white", edgecolor=color, lw=0.9))
        ax.text(0.06, y - 0.008, short_name(row["standardized_feature_name"], 44), transform=ax.transAxes, fontsize=6.3, va="center")
        ax.text(0.72, y - 0.008, row["omics_layer"], transform=ax.transAxes, fontsize=5.8, color=COLORS["grey"], va="center")
        ax.text(0.88, y - 0.008, "? direction", transform=ax.transAxes, fontsize=5.8, color=COLORS["grey"], va="center")
        y -= 0.075
    if subset.empty:
        ax.text(0.5, 0.45, "No resolved Tier I feature assigned", transform=ax.transAxes, ha="center", fontsize=8, color=COLORS["grey"])
    ax.text(0.02, 0.06, "Interpretive module zoom; arrows/labels are not direct proof.", transform=ax.transAxes, fontsize=6.2, color=COLORS["grey"])
    write_panel_trace(
        panel,
        [{"displayed_element": title, "displayed_value": len(subset), "source_column": "assigned_figure4_module; assignment_status; direction", "source_row_or_rule": f"Resolved module == {module}; unresolved features excluded.", "verification_status": "limited_evidence"}],
    )
    save_panel(fig, panel_output_paths(panel))


def panel_d() -> None:
    module_panel("D", "SCFA / butyrate module zoom-in", MODULE_ORDER[0], "butyrate-producing taxa -> SCFA availability -> epithelial barrier support")


def panel_e() -> None:
    module_panel("E", "Bile acid module zoom-in", MODULE_ORDER[1], "bile acid conversion and host-microbial metabolic coupling")


def panel_f() -> None:
    module_panel("F", "Amino acid / aromatic amino acid module", MODULE_ORDER[2], "amino-acid availability and aromatic microbial-host co-metabolism")


def panel_g() -> None:
    module_panel("G", "Oxidative-stress lipid module", MODULE_ORDER[3], "core node with supporting evidence ring; no extra features added")


def panel_h() -> None:
    master = load_master_table()
    stages = ["Diagnosis", "Active", "Remission/residual", "Relapse-related", "Post-treatment"]
    fields = ["diagnosis_evidence", "active_evidence", "remission_evidence", "relapse_evidence", "post_treatment_evidence"]
    rows = []
    for stage, field in zip(stages, fields):
        for module in MODULE_ORDER:
            subset = master[master["assigned_figure4_module"] == module]
            direct = int((subset[field] == "direct comparison support").sum())
            limited = int(subset[field].astype(str).str.contains("limited").sum())
            rows.append({"stage": stage, "module": module, "direct_count": direct, "limited_count": limited})
    table = pd.DataFrame(rows)
    table.to_csv(panel_output_paths("H")["trace"].parent / "panel_H_stage_module_matrix.csv", index=False, encoding="utf-8-sig")
    fig, ax = new_panel(118, 70)
    add_panel_letter(fig, "H")
    ax.axis("off")
    ax.text(0.02, 0.94, "Stage-related fingerprint summary", transform=ax.transAxes, fontsize=8.5, fontweight="bold")
    x0, y0 = 0.23, 0.78
    for j, module in enumerate(MODULE_ORDER):
        ax.text(x0 + j * 0.18, y0 + 0.08, module.split(" / ")[0].replace("Oxidative", "Oxid."), transform=ax.transAxes, ha="center", fontsize=5.7, fontweight="bold")
    for i, stage in enumerate(stages):
        y = y0 - i * 0.13
        ax.text(0.02, y, stage, transform=ax.transAxes, fontsize=6.2, va="center")
        for j, module in enumerate(MODULE_ORDER):
            rec = table[(table["stage"] == stage) & (table["module"] == module)].iloc[0]
            text = f"D{rec.direct_count}" if rec.direct_count else f"L{rec.limited_count}" if rec.limited_count else "NA"
            color = COLORS["blue"] if rec.direct_count else COLORS["grey_line"] if rec.limited_count else COLORS["grey_light"]
            ax.add_patch(patches.Rectangle((x0 - 0.055 + j * 0.18, y - 0.04), 0.11, 0.07, transform=ax.transAxes, facecolor=color, edgecolor="white"))
            ax.text(x0 + j * 0.18, y - 0.004, text, transform=ax.transAxes, ha="center", va="center", fontsize=6.0, color="white" if rec.direct_count else COLORS["black"])
    ax.text(0.02, 0.05, "D = direct comparison-supported count; L = limited evidence count; NA = not available.", transform=ax.transAxes, fontsize=6.2, color=COLORS["grey"])
    write_panel_trace(
        "H",
        [{"displayed_element": "stage x module evidence matrix", "displayed_value": "D/L/NA", "source_column": "diagnosis_evidence; active_evidence; remission_evidence; relapse_evidence; post_treatment_evidence", "source_row_or_rule": "Limited states are explicitly encoded.", "verification_status": "limited_evidence"}],
    )
    save_panel(fig, panel_output_paths("H"))


def panel_i() -> None:
    fig, ax = new_panel(118, 58)
    add_panel_letter(fig, "I")
    ax.axis("off")
    ax.text(0.03, 0.92, "Hierarchical coupling model", transform=ax.transAxes, fontsize=8.5, fontweight="bold")
    layers = [
        ("Ecological\ndysbiosis", "microbiome niche"),
        ("Metabolic\ndisturbance", "SCFA / bile acid /\namino-acid / lipid"),
        ("Reduced barrier\nsupport", "weaker epithelial\nsupport"),
        ("Immune-inflammatory\namplification", "inflammatory\namplification"),
    ]
    x_positions = [0.15, 0.38, 0.61, 0.84]
    for idx, ((title, subtitle), x) in enumerate(zip(layers, x_positions)):
        ax.add_patch(patches.FancyBboxPatch((x - 0.085, 0.40), 0.17, 0.26, boxstyle="round,pad=0.006,rounding_size=0.014", transform=ax.transAxes, facecolor=COLORS["grey_light"] if idx != 1 else "#E8F0F7", edgecolor=COLORS["blue"], lw=0.9))
        ax.text(x, 0.565, title, transform=ax.transAxes, ha="center", va="center", fontsize=5.3, fontweight="bold", linespacing=0.95)
        ax.text(x, 0.455, subtitle, transform=ax.transAxes, ha="center", va="center", fontsize=4.5, color=COLORS["grey"], linespacing=0.95)
        if idx < len(x_positions) - 1:
            ax.annotate("", xy=(x_positions[idx + 1] - 0.095, 0.53), xytext=(x + 0.095, 0.53), xycoords=ax.transAxes, arrowprops={"arrowstyle": "-|>", "lw": 0.8, "color": COLORS["grey_line"]})
    ax.text(0.5, 0.18, "Proposed coupling; consistent with integrated evidence. Not a direct proof.", transform=ax.transAxes, ha="center", fontsize=6.6, color=COLORS["grey"])
    write_panel_trace(
        "I",
        [{"displayed_element": "hierarchical coupling model", "displayed_value": "proposed coupling", "source_column": "stage matrix hierarchical coupling sheet", "source_row_or_rule": "Conceptual framework; no statistical numbers shown.", "verification_status": "limited_evidence"}],
    )
    save_panel(fig, panel_output_paths("I"))


def build_all() -> None:
    ensure_directories()
    write_source_hash_snapshot()
    build_master_table()
    for func in [panel_a, panel_b, panel_c, panel_d, panel_e, panel_f, panel_g, panel_h, panel_i]:
        func()
    status = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "panel_status": {panel: {"panel_status": status, "fallback_reason": reason} for panel, (status, reason) in PANEL_STATUS.items()},
    }
    (LOG_DIR / "figure4_build_status.json").write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    build_all()
