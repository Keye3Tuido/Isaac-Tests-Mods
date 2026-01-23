# BD.py
import os
import glob
import json
import re
import io
from math import atan2, degrees, sqrt

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import norm, binomtest

# --- Configuration / Groups ---
BD_GROUPS = ["BD", "BDXL", "BDKp", "BDXLKp"]
BDI_GROUPS = ["BDI", "BDIXL", "BDIKp", "BDIXLKp"]
N_VALUES = [1, 2, 3, 4, 5, 6, 7]  # fixed 1..7

DOOR_KEYS = ["Left", "Up", "Right", "Down"]
DIRECTION_KEYS = ["Left", "Up-Left", "Up", "Up-Right", "Right", "Down-Right", "Down", "Down-Left"]
DIR_COLS = [f"Dir_{k.replace('-', '_')}" for k in DIRECTION_KEYS]


# --- Utility functions ---
def sort_key(exp_id):
    match = re.match(r"(\d+)([a-zA-Z]*)", exp_id)
    if match:
        num = int(match.group(1))
        suffix = match.group(2)
        return (num, suffix)
    else:
        return (float("inf"), exp_id)


def angle_cw(dx, dy):
    ang = degrees(atan2(dy, dx))
    return -ang


def get_direction(angle):
    if (-180 <= angle < -157.5) or (157.5 <= angle <= 180):
        return "Left"
    elif -157.5 <= angle < -112.5:
        return "Up_Left"
    elif -112.5 <= angle < -67.5:
        return "Up"
    elif -67.5 <= angle < -22.5:
        return "Up_Right"
    elif -22.5 <= angle < 22.5:
        return "Right"
    elif 22.5 <= angle < 67.5:
        return "Down_Right"
    elif 67.5 <= angle < 112.5:
        return "Down"
    elif 112.5 <= angle < 157.5:
        return "Down_Left"
    return "Left"


def plot_grid(exp_id, probs):
    size = 13
    cx, cy = size // 2, size // 2
    fig, ax = plt.subplots(figsize=(4, 4))
    colors = {
        "Left": "#f28b82", "Up_Left": "#fbbc04", "Up": "#fff475", "Up_Right": "#ccff90",
        "Right": "#a7ffeb", "Down_Right": "#cbf0f8", "Down": "#aecbfa", "Down_Left": "#d7aefb"
    }
    label_pos = {
        "Left": (-5, 0),
        "Up_Left": (-4, 4),
        "Up": (0, 5),
        "Up_Right": (4, 4),
        "Right": (5, 0),
        "Down_Right": (4, -4),
        "Down": (0, -5),
        "Down_Left": (-4, -4),
    }
    for x in range(size):
        for y in range(size):
            dx, dy = x - cx, y - cy
            if dx == 0 and dy == 0:
                ax.add_patch(plt.Rectangle((x, y), 1, 1, facecolor="white", edgecolor="black", linewidth=0.5))
                continue
            ang = angle_cw(dx, dy)
            dir_name = get_direction(ang)
            face = colors.get(dir_name, "#ffffff")
            ax.add_patch(plt.Rectangle((x, y), 1, 1, facecolor=face, edgecolor="black", linewidth=0.5))
    ax.set_xlim(0, size)
    ax.set_ylim(0, size)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(exp_id)
    for d, (x_off, y_off) in label_pos.items():
        key = f"Dir_{d}"
        val = probs.get(key, None)
        if val is not None:
            ax.text(cx + x_off, cy + y_off, f"{val * 100:.2f}%", fontsize=8, ha="center", va="center", color="black")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def plot_doors(exp_id, door_probs):
    fig, ax = plt.subplots(figsize=(2.4, 2.4))
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 3)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal")
    positions = {
        "Up": (1, 2),
        "Left": (0, 1),
        "Right": (2, 1),
        "Down": (1, 0),
        "Center": (1, 1)
    }
    for key, (x, y) in positions.items():
        if key == "Center":
            ax.add_patch(plt.Rectangle((x, y), 1, 1, facecolor="white", edgecolor="black", linewidth=0.8))
            ax.text(x + 0.5, y + 0.5, f"{exp_id}", ha="center", va="center", fontsize=10, color="black")
        else:
            ax.add_patch(plt.Rectangle((x, y), 1, 1, facecolor="#f0f0f0", edgecolor="black", linewidth=0.8))
            val = door_probs.get(key, 0.0)
            ax.text(x + 0.5, y + 0.5, f"{val * 100:.2f}%", ha="center", va="center", fontsize=9, color="black")
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def get_z(alpha):
    return norm.ppf(1 - alpha / 2)


def wilson_interval(N, A, alpha):
    z = get_z(alpha)
    if N == 0:
        return 0.0, 1.0
    p_hat = A / N
    denom = 1 + z * z / N
    center = p_hat + (z * z) / (2 * N)
    rad = z * sqrt(max(0.0, p_hat * (1 - p_hat) / N + (z * z) / (4 * N * N)))
    lower = (center - rad) / denom
    upper = (center + rad) / denom
    return max(0.0, lower), min(1.0, upper)


def verify_confidence(N, counts, alpha):
    results = []
    for label, A in counts.items():
        p_hat = A / N if N > 0 else 0.0
        lower, upper = wilson_interval(N, A, alpha)
        margin = max(p_hat - lower, upper - p_hat)
        results.append({
            "类别": label,
            "频数": int(A),
            "估计概率": round(p_hat, 6),
            "下界": round(lower, 6),
            "上界": round(upper, 6),
            "误差幅度": round(margin, 6),
            "≤1%": bool(margin <= 0.01)
        })
    return results


def pairwise_significant_higher_group(counts, labels_in_group, overall_alpha=0.05):
    labels = [lab for lab in labels_in_group if lab in counts]
    n = len(labels)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append((labels[i], labels[j]))
    m_tests = len(pairs)
    if m_tests == 0:
        return []
    alpha_per_test = overall_alpha / m_tests
    conclusions = []
    for a, b in pairs:
        A = int(counts.get(a, 0))
        B = int(counts.get(b, 0))
        m = A + B
        if m == 0:
            continue
        res_ab = binomtest(A, n=m, p=0.5, alternative='greater')
        p_ab = res_ab.pvalue
        if p_ab <= alpha_per_test:
            conclusions.append({
                "conclusion": f"{a}>{b}",
                "p_value": float(p_ab),
                "A_count": A,
                "B_count": B,
                "diff_conditional": round((A / m) - (B / m), 6)
            })
            continue
        res_ba = binomtest(B, n=m, p=0.5, alternative='greater')
        p_ba = res_ba.pvalue
        if p_ba <= alpha_per_test:
            conclusions.append({
                "conclusion": f"{b}>{a}",
                "p_value": float(p_ba),
                "A_count": B,
                "B_count": A,
                "diff_conditional": round((B / m) - (A / m), 6)
            })
            continue
    return conclusions


# --- Version extraction helper ---
def extract_version_from_name(name):
    """
    Extract version like '3.19w' -> 3.19 (float). Returns None if not found.
    """
    m = re.search(r"(\d+\.\d+)w", name)
    if not m:
        return None
    try:
        return float(m.group(1))
    except:
        return None


def summarize_num(lst):
    """
    Given a list of numeric versions (floats), return the mode as float, or None if empty.
    """
    if not lst:
        return None
    vals, counts = np.unique(np.array(lst), return_counts=True)
    return float(vals[np.argmax(counts)])


def n_to_bits_t102_low(n):
    """
    Map N (1..7) to bits with t102 as low bit:
      - t102 = bit 0 (2^0)
      - c599 = bit 1 (2^1)
      - c589 = bit 2 (2^2)
    Returns tuple (c589, c599, t102)
    """
    t102 = n & 1
    c599 = (n >> 1) & 1
    c589 = (n >> 2) & 1
    return (c589, c599, t102)


def _layers_from_group_files(files):
    """
    For each dat file in files, count how many experiment entries contain 'Total'.
    Return the mode (most common) per-file count as string, or "" if none.
    """
    counts = []
    for full in files:
        try:
            with open(full, "r", encoding="utf-8") as f:
                data = json.load(f)
            c = sum(1 for exp in data.values() if isinstance(exp, dict) and ("Total" in exp))
            if c > 0:
                counts.append(c)
        except Exception:
            continue
    if not counts:
        return ""
    vals, freqs = np.unique(np.array(counts), return_counts=True)
    return str(int(vals[np.argmax(freqs)]))


# --- Single-file conversion (adapted from provided logic) ---
def process_dat_in_current_dir_single(dat_path):
    """
    Process a single .dat file (full path). Write an .xlsx with same base name in same directory.
    Returns True if xlsx was created, False otherwise.
    """
    try:
        with open(dat_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to read {dat_path}: {e}")
        return False

    sorted_ids = sorted(data.keys(), key=sort_key)
    rows = []
    for exp_id in sorted_ids:
        exp = data[exp_id]
        row = {"ID": exp_id}
        for k in DOOR_KEYS:
            row[f"Door_{k}"] = exp.get("Doors", {}).get(k, 0)
        row["Total"] = exp.get("Total", 0)
        for k in DIRECTION_KEYS:
            row[f"Dir_{k.replace('-', '_')}"] = exp.get("Directions", {}).get(k, 0)
        rows.append(row)

    if not rows:
        return False

    df_data = pd.DataFrame(rows)
    # probabilities
    df_prob = df_data.copy()
    totals = df_data["Total"].replace(0, np.nan)
    for k in DOOR_KEYS:
        df_prob[f"Door_{k}"] = df_data[f"Door_{k}"] / totals
    for k in DIRECTION_KEYS:
        df_prob[f"Dir_{k.replace('-', '_')}"] = df_data[f"Dir_{k.replace('-', '_')}"] / totals
    df_prob[[f"Door_{k}" for k in DOOR_KEYS] + DIR_COLS] = df_prob[[f"Door_{k}" for k in DOOR_KEYS] + DIR_COLS].fillna(0)

    # normalization / deviation tables
    df_norm = pd.DataFrame()
    df_norm["ID"] = df_prob["ID"]
    door_cols = [f"Door_{k}" for k in DOOR_KEYS]
    door_probs_nonzero = df_prob[door_cols].replace(0, np.nan)
    df_norm["Door_mean"] = door_probs_nonzero.mean(axis=1, skipna=True).fillna(0)
    for k in DOOR_KEYS:
        col = f"Door_{k}"
        df_norm[f"{col}(%)"] = (df_prob[col] - df_norm["Door_mean"]) * 100
    df_norm["Door_var(%^2)"] = door_probs_nonzero.mul(100).var(axis=1, ddof=0, skipna=True).fillna(0)
    df_norm["Door_std(%)"] = np.sqrt(df_norm["Door_var(%^2)"])

    # straight directions
    dir_straight = [f"Dir_{k.replace('-', '_')}" for k in ["Left", "Up", "Right", "Down"]]
    dir_straight_nonzero = df_prob[dir_straight].replace(0, np.nan)
    df_norm["Dir_straight_mean"] = dir_straight_nonzero.mean(axis=1, skipna=True).fillna(0)
    for col in dir_straight:
        df_norm[f"{col}(%)"] = (df_prob[col] - df_norm["Dir_straight_mean"]) * 100
    df_norm["Dir_straight_var(%^2)"] = dir_straight_nonzero.mul(100).var(axis=1, ddof=0, skipna=True).fillna(0)
    df_norm["Dir_straight_std(%)"] = np.sqrt(df_norm["Dir_straight_var(%^2)"])

    # diagonal directions
    diag_keys = ["Up-Left", "Up-Right", "Down-Right", "Down-Left"]
    dir_diagonal = [f"Dir_{k.replace('-', '_')}" for k in diag_keys]
    dir_diagonal_nonzero = df_prob[dir_diagonal].replace(0, np.nan)
    df_norm["Dir_diagonal_mean"] = dir_diagonal_nonzero.mean(axis=1, skipna=True).fillna(0)
    for col in dir_diagonal:
        df_norm[f"{col}(%)"] = (df_prob[col] - df_norm["Dir_diagonal_mean"]) * 100
    df_norm["Dir_diagonal_var(%^2)"] = dir_diagonal_nonzero.mul(100).var(axis=1, ddof=0, skipna=True).fillna(0)
    df_norm["Dir_diagonal_std(%)"] = np.sqrt(df_norm["Dir_diagonal_var(%^2)"])

    df_norm["Dir_combined_std(%)"] = np.sqrt(df_norm["Dir_straight_var(%^2)"] + df_norm["Dir_diagonal_var(%^2)"])

    ordered_cols = (
        ["ID", "Door_mean"]
        + [f"Door_{k}(%)" for k in DOOR_KEYS]
        + ["Door_var(%^2)", "Door_std(%)",
           "Dir_straight_mean"]
        + [f"Dir_{k}(%)" for k in ["Left", "Up", "Right", "Down"]]
        + ["Dir_straight_var(%^2)", "Dir_straight_std(%)",
           "Dir_diagonal_mean"]
        + [f"Dir_{k.replace('-', '_')}(%)" for k in ["Up-Left", "Up-Right", "Down-Right", "Down-Left"]]
        + ["Dir_diagonal_var(%^2)", "Dir_diagonal_std(%)",
           "Dir_combined_std(%)"]
    )
    ordered_cols = [c for c in ordered_cols if c in df_norm.columns]
    df_norm = df_norm[ordered_cols]

    # prepare output path
    out_dir = os.path.dirname(dat_path)
    base_name = os.path.splitext(os.path.basename(dat_path))[0]
    out_file = os.path.join(out_dir, f"{base_name}.xlsx")

    try:
        with pd.ExcelWriter(out_file, engine="xlsxwriter") as writer:
            df_data.to_excel(writer, sheet_name="实验数据", index=False)
            df_prob.to_excel(writer, sheet_name="概率统计", index=False)
            df_norm.to_excel(writer, sheet_name="均值偏差(%)方差", index=False)
            workbook = writer.book

            # create image sheets and CI/summary sheets
            worksheet_doors = workbook.add_worksheet("门概率图")
            writer.sheets["门概率图"] = worksheet_doors
            worksheet_dirs = workbook.add_worksheet("方向图")
            writer.sheets["方向图"] = worksheet_dirs

            # insert door images grouped by numeric prefix
            groups = {}
            for exp_id in sorted_ids:
                m = re.match(r"(\d+)", exp_id)
                num = m.group(1) if m else exp_id
                groups.setdefault(num, []).append(exp_id)

            col_unit = 4
            for group_idx, (num, exp_ids) in enumerate(groups.items()):
                for j, exp_id in enumerate(exp_ids):
                    row = df_prob.loc[df_prob["ID"] == exp_id]
                    door_probs = {}
                    for k in DOOR_KEYS:
                        col = f"Door_{k}"
                        door_probs[k] = (row.iloc[0][col] if not row.empty and col in row.columns else 0.0)
                    buf = plot_doors(exp_id, door_probs)
                    r = group_idx * 12
                    c = j * col_unit
                    worksheet_doors.insert_image(r, c, f"{exp_id}_doors.png", {"image_data": buf})

            # direction images
            row_offset = 0
            for group_idx, (num, exp_ids) in enumerate(groups.items()):
                col_offset = 0
                for exp_id in exp_ids:
                    row = df_prob.loc[df_prob["ID"] == exp_id]
                    probs = {}
                    for col in DIR_COLS:
                        probs[col] = (row.iloc[0][col] if not row.empty and col in row.columns else 0.0)
                    buf = plot_grid(exp_id, probs)
                    worksheet_dirs.insert_image(row_offset, col_offset, exp_id + ".png", {"image_data": buf})
                    col_offset += 6
                row_offset += 20

            # CI sheet
            worksheet_ci = workbook.add_worksheet("置信区间验证")
            writer.sheets["置信区间验证"] = worksheet_ci
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1'})
            row_offset = 0
            for exp_id in sorted_ids:
                exp = data[exp_id]
                N = exp.get("Total", 0)
                # Doors
                alpha_doors = 0.05 / 4
                door_counts = {k: exp.get("Doors", {}).get(k, 0) for k in DOOR_KEYS}
                door_results = verify_confidence(N, door_counts, alpha_doors)
                worksheet_ci.write(row_offset, 0, f"实验 {exp_id} - Doors", header_fmt)
                row_offset += 1
                headers = ["类别", "频数", "估计概率", "下界", "上界", "误差幅度", "≤1%"]
                for col_idx, h in enumerate(headers):
                    worksheet_ci.write(row_offset, col_idx, h, header_fmt)
                row_offset += 1
                for r in door_results:
                    for col_idx, h in enumerate(headers):
                        worksheet_ci.write(row_offset, col_idx, r[h])
                    row_offset += 1
                row_offset += 1
                # Directions
                alpha_dirs = 0.05 / 8
                dir_counts = {k: exp.get("Directions", {}).get(k, 0) for k in DIRECTION_KEYS}
                dir_results = verify_confidence(N, dir_counts, alpha_dirs)
                worksheet_ci.write(row_offset, 0, f"实验 {exp_id} - Directions", header_fmt)
                row_offset += 1
                for col_idx, h in enumerate(headers):
                    worksheet_ci.write(row_offset, col_idx, h, header_fmt)
                row_offset += 1
                for r in dir_results:
                    for col_idx, h in enumerate(headers):
                        worksheet_ci.write(row_offset, col_idx, r[h])
                    row_offset += 1
                row_offset += 2

            # Summary sheets (conclusions)
            worksheet_summary_doors = workbook.add_worksheet("结论-门")
            writer.sheets["结论-门"] = worksheet_summary_doors
            worksheet_summary_dirs = workbook.add_worksheet("结论-方向")
            writer.sheets["结论-方向"] = worksheet_summary_dirs
            header_row = ["实验编号", "结论", "p_value", "A_count", "B_count", "差值(pA-pB, N分母)"]
            for col_idx, h in enumerate(header_row):
                worksheet_summary_doors.write(0, col_idx, h, header_fmt)
                worksheet_summary_dirs.write(0, col_idx, h, header_fmt)
            row_d = 1
            row_dir = 1
            for exp_id in sorted_ids:
                exp = data[exp_id]
                N = exp.get("Total", 0)
                door_counts = {k: exp.get("Doors", {}).get(k, 0) for k in DOOR_KEYS}
                door_conclusions = pairwise_significant_higher_group(door_counts, DOOR_KEYS, overall_alpha=0.05)
                for item in door_conclusions:
                    A = item["A_count"]
                    B = item["B_count"]
                    diff_total = (A / N - B / N) if N > 0 else 0.0
                    worksheet_summary_doors.write_row(row_d, 0, [
                        exp_id,
                        item["conclusion"],
                        item["p_value"],
                        item["A_count"],
                        item["B_count"],
                        round(diff_total, 6)
                    ])
                    row_d += 1
                dir_counts = {k: exp.get("Directions", {}).get(k, 0) for k in DIRECTION_KEYS}
                straight_labels = ["Left", "Up", "Right", "Down"]
                straight_conclusions = pairwise_significant_higher_group(dir_counts, straight_labels, overall_alpha=0.05)
                for item in straight_conclusions:
                    A = item["A_count"]
                    B = item["B_count"]
                    diff_total = (A / N - B / N) if N > 0 else 0.0
                    worksheet_summary_dirs.write_row(row_dir, 0, [
                        exp_id,
                        item["conclusion"],
                        item["p_value"],
                        item["A_count"],
                        item["B_count"],
                        round(diff_total, 6)
                    ])
                    row_dir += 1
                diagonal_labels = ["Up-Left", "Up-Right", "Down-Right", "Down-Left"]
                diagonal_conclusions = pairwise_significant_higher_group(dir_counts, diagonal_labels, overall_alpha=0.05)
                for item in diagonal_conclusions:
                    A = item["A_count"]
                    B = item["B_count"]
                    diff_total = (A / N - B / N) if N > 0 else 0.0
                    worksheet_summary_dirs.write_row(row_dir, 0, [
                        exp_id,
                        item["conclusion"],
                        item["p_value"],
                        item["A_count"],
                        item["B_count"],
                        round(diff_total, 6)
                    ])
                    row_dir += 1

            # conditional formatting for diff columns (if any rows)
            try:
                diff_col_idx = 5
                if row_d - 1 >= 1:
                    worksheet_summary_doors.conditional_format(1, diff_col_idx, row_d - 1, diff_col_idx,
                                                              {'type': 'cell', 'criteria': '<', 'value': 0.01,
                                                               'format': workbook.add_format({'bg_color': '#D9D9D9'})})
                    worksheet_summary_doors.conditional_format(1, diff_col_idx, row_d - 1, diff_col_idx,
                                                              {'type': 'cell', 'criteria': 'between', 'minimum': 0.01,
                                                               'maximum': 0.02,
                                                               'format': workbook.add_format({'bg_color': '#FFD966'})})
                    worksheet_summary_doors.conditional_format(1, diff_col_idx, row_d - 1, diff_col_idx,
                                                              {'type': 'cell', 'criteria': '>=', 'value': 0.02,
                                                               'format': workbook.add_format({'bg_color': '#A9D08E'})})
                if row_dir - 1 >= 1:
                    worksheet_summary_dirs.conditional_format(1, diff_col_idx, row_dir - 1, diff_col_idx,
                                                              {'type': 'cell', 'criteria': '<', 'value': 0.01,
                                                               'format': workbook.add_format({'bg_color': '#D9D9D9'})})
                    worksheet_summary_dirs.conditional_format(1, diff_col_idx, row_dir - 1, diff_col_idx,
                                                              {'type': 'cell', 'criteria': 'between', 'minimum': 0.01,
                                                               'maximum': 0.02,
                                                               'format': workbook.add_format({'bg_color': '#FFD966'})})
                    worksheet_summary_dirs.conditional_format(1, diff_col_idx, row_dir - 1, diff_col_idx,
                                                              {'type': 'cell', 'criteria': '>=', 'value': 0.02,
                                                               'format': workbook.add_format({'bg_color': '#A9D08E'})})
            except Exception:
                pass

    except Exception as e:
        print(f"Failed to write {out_file}: {e}")
        return False

    print(f"{out_file} 已生成.")
    return True


# --- statistics.md generation ---
def generate_statistics_md(base_dir):
    base_dir = os.path.abspath(base_dir)
    group_files = {g: [] for g in BD_GROUPS + BDI_GROUPS}
    bdi_detail = {g: {n: [] for n in N_VALUES} for g in BDI_GROUPS}

    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if not f.lower().endswith(".dat"):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, base_dir)
            parts = rel.split(os.sep)
            if len(parts) < 2:
                continue
            group = parts[0]
            if group not in group_files:
                continue
            group_files[group].append(full)
            if group in BDI_GROUPS and len(parts) >= 2:
                sub = parts[1]
                if re.fullmatch(r"\d+", sub):
                    n = int(sub)
                    if n in N_VALUES:
                        bdi_detail[group][n].append(full)

    lines = []
    # First table header
    lines.append("| # | layers | rep(w) | rep+(w) |")
    lines.append("|:--:|:--:|:--:|:--:|")

    rep_sum_1 = 0.0
    rplus_sum_1 = 0.0

    for g in BD_GROUPS:
        files = group_files.get(g, [])
        layers = _layers_from_group_files(files)
        rep_versions = []
        rplus_versions = []
        for full in files:
            name = os.path.basename(full)
            v = extract_version_from_name(name)
            if v is None:
                continue
            lower = name.lower()
            if "rep" in lower and "r+" not in lower:
                rep_versions.append(v)
            if "r+" in lower:
                rplus_versions.append(v)
        rep_v_num = summarize_num(rep_versions)
        rplus_v_num = summarize_num(rplus_versions)
        rep_v = f"{rep_v_num:.2f}" if rep_v_num is not None else ""
        rplus_v = f"{rplus_v_num:.2f}" if rplus_v_num is not None else ""
        if rep_v_num is not None:
            rep_sum_1 += rep_v_num
        if rplus_v_num is not None:
            rplus_sum_1 += rplus_v_num
        lines.append(f"| {g} | {layers} | {rep_v} | {rplus_v} |")

    # Append Total row for first table
    rep_sum_1_str = f"{rep_sum_1:.2f}" if rep_sum_1 != 0 else "0.00"
    rplus_sum_1_str = f"{rplus_sum_1:.2f}" if rplus_sum_1 != 0 else "0.00"
    lines.append(f"| Total |  | {rep_sum_1_str} | {rplus_sum_1_str} |")
    lines.append("")

    # Second table header
    lines.append("| # | layers | N | c589 | c599 | t102 | rep(w) | rep+(w) |")
    lines.append("|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|")

    rep_sum_2 = 0.0
    rplus_sum_2 = 0.0

    for g in BDI_GROUPS:
        files_all = group_files.get(g, [])
        layers = _layers_from_group_files(files_all)
        first_row = True
        for n in N_VALUES:
            n_str = str(n)
            files_n = bdi_detail[g][n]
            b_c589, b_c599, b_t102 = n_to_bits_t102_low(n)
            rep_versions = []
            rplus_versions = []
            for full in files_n:
                name = os.path.basename(full)
                v = extract_version_from_name(name)
                if v is None:
                    continue
                lower = name.lower()
                if "rep" in lower and "r+" not in lower:
                    rep_versions.append(v)
                if "r+" in lower:
                    rplus_versions.append(v)
            rep_v_num = summarize_num(rep_versions)
            rplus_v_num = summarize_num(rplus_versions)
            rep_v = f"{rep_v_num:.2f}" if rep_v_num is not None else ""
            rplus_v = f"{rplus_v_num:.2f}" if rplus_v_num is not None else ""
            if rep_v_num is not None:
                rep_sum_2 += rep_v_num
            if rplus_v_num is not None:
                rplus_sum_2 += rplus_v_num
            if first_row:
                g_cell = g
                layers_cell = layers
                first_row = False
            else:
                g_cell = ""
                layers_cell = ""
            lines.append(
                f"| {g_cell} | {layers_cell} | {n_str} | {b_c589} | {b_c599} | {b_t102} | {rep_v} | {rplus_v} |"
            )

    rep_sum_2_str = f"{rep_sum_2:.2f}" if rep_sum_2 != 0 else "0.00"
    rplus_sum_2_str = f"{rplus_sum_2:.2f}" if rplus_sum_2 != 0 else "0.00"
    lines.append(f"| Total |  |  |  |  |  | {rep_sum_2_str} | {rplus_sum_2_str} |")

    md_path = os.path.join(base_dir, "statistics.md")
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("statistics.md 已生成:", md_path)
    except Exception as e:
        print("写入 statistics.md 失败:", e)
    return md_path


# --- Recursive processing entrypoint (Mode A: per-file) ---
def process_all_dat_files(base_dir):
    """
    Mode A: scan all .dat files recursively and convert each file individually.
    Returns dict with created/skipped lists and statistics_md path.
    """
    base_dir = os.path.abspath(base_dir)
    created = []
    skipped = []

    # collect all dat files
    dat_files = []
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith(".dat"):
                dat_files.append(os.path.join(root, f))

    for dat_path in dat_files:
        out_dir = os.path.dirname(dat_path)
        base_name = os.path.splitext(os.path.basename(dat_path))[0]
        xlsx_path = os.path.join(out_dir, f"{base_name}.xlsx")

        # If xlsx already exists, skip conversion for this file
        if os.path.exists(xlsx_path):
            skipped.append(xlsx_path)
            continue

        # Convert single file
        ok = process_dat_in_current_dir_single(dat_path)
        if ok and os.path.exists(xlsx_path):
            created.append(xlsx_path)
        else:
            # conversion failed or didn't produce file
            skipped.append(xlsx_path)

    # regenerate statistics.md after conversions
    md_path = generate_statistics_md(base_dir)
    return {"created": created, "skipped": skipped, "statistics_md": md_path}


# --- CLI entrypoint ---
if __name__ == "__main__":
    base = os.getcwd()
    print("Processing dat files under:", base)
    res = process_all_dat_files(base)
    print("created:", len(res["created"]))
    print("skipped:", len(res["skipped"]))
    print("statistics_md:", res["statistics_md"])
