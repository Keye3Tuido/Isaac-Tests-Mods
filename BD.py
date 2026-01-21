import glob
import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import re
import io
import numpy as np
from math import atan2, degrees, sqrt
from scipy.stats import norm, binomtest, binom

door_keys = ["Left", "Up", "Right", "Down"]
direction_keys = ["Left", "Up-Left", "Up", "Up-Right", "Right", "Down-Right", "Down", "Down-Left"]

def sort_key(exp_id):
    match = re.match(r"(\d+)([a-z]*)", exp_id)
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

colors = {
    "Left":"red","Up_Left":"orange","Up":"yellow","Up_Right":"green",
    "Right":"cyan","Down_Right":"blue","Down":"purple","Down_Left":"pink"
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

def plot_grid(exp_id, probs):
    size = 13
    cx, cy = size // 2, size // 2
    fig, ax = plt.subplots(figsize=(4, 4))
    for x in range(size):
        for y in range(size):
            dx, dy = x - cx, y - cy
            if dx == 0 and dy == 0:
                ax.add_patch(plt.Rectangle((x, y), 1, 1, facecolor="white", edgecolor="black", linewidth=0.5))
                continue
            ang = angle_cw(dx, dy)
            dir_name = get_direction(ang)
            face = colors[dir_name]
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
    fig, ax = plt.subplots(figsize=(2.4,2.4))
    ax.set_xlim(0,3)
    ax.set_ylim(0,3)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_aspect("equal")
    positions = {
        "Up": (1,2),
        "Left": (0,1),
        "Right": (2,1),
        "Down": (1,0),
        "Center": (1,1)
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
    return norm.ppf(1 - alpha/2)

def wilson_interval(N, A, alpha):
    z = get_z(alpha)
    if N == 0:
        return 0.0, 1.0
    p_hat = A / N
    denom = 1 + z*z/N
    center = p_hat + (z*z)/(2*N)
    rad = z * sqrt(max(0.0, p_hat*(1-p_hat)/N + (z*z)/(4*N*N)))
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
        for j in range(i+1, n):
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
                "diff_conditional": round((A/m) - (B/m), 6)
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
                "diff_conditional": round((B/m) - (A/m), 6)
            })
            continue
    return conclusions

dir_cols = [f"Dir_{k.replace('-', '_')}" for k in direction_keys]

def write_formula_block_merged(worksheet, sheet_type, workbook, max_merge_cols=5):
    common_lines = [
        "计算说明（本节列出脚本中用于计算与检验的公式与步骤，便于复现）：",
        "",
        "1) 概率估计",
        "   - 观测计数 A_i 为某类别的观测次数，总试验次数为 N（或在两类比较中为 m = A + B）。",
        "   - 类别的估计概率： p_hat = A / N （若只比较两类，则条件概率 p_hat = A / m）。",
        "",
        "2) Wilson 置信区间（用于单个类别概率的置信区间，双侧）",
        "   - 给定显著性水平 alpha（双侧），先计算 z = Phi^{-1}(1 - alpha/2)。",
        "   - 设 p_hat = A / N，",
        "     denom = 1 + z^2 / N",
        "     center = p_hat + z^2 / (2N)",
        "     rad = z * sqrt( p_hat*(1-p_hat)/N + z^2/(4N^2) )",
        "     下界 lower = (center - rad) / denom",
        "     上界 upper = (center + rad) / denom",
        "   - 区间被截断到 [0,1]。",
        "",
        "3) 两类显著性比较（用于判断 A > B）",
        "   - 只看落在 A 或 B 的样本，令 m = A + B。",
        "   - 在原假设 H0: p_A = p_B（条件下 p = 0.5）下，A ~ Binomial(m, 0.5)。",
        "   - 使用精确二项检验（binomtest）做单侧检验：H1: p_A > 0.5（即 A 的条件概率大于 B）。",
        "   - 得到单侧 p_value（脚本中称为原始 p_value）。",
        "",
        "4) 多重比较校正（组内 Bonferroni）",
        "   - 在同一组（例如门组或某方向子组）内做所有两两比较，若组内共有 T 个两两比较，",
        "     则每次检验的显著性阈值设为 alpha_per_test = overall_alpha / T（overall_alpha 默认为 0.05）。",
        "   - 仅当单侧 p_value <= alpha_per_test 时，记录显著结论 A>B（或 B>A）。",
        "",
        "5) 差值与效应量（使用总样本 N 作为分母）",
        "   - 在两类比较中，差值定义为：",
        "       diff_total = (A/N) - (B/N)，其中 N 为总样本量。",
        "   - 这样差值直接反映在总样本中的概率差异，便于与“误差 ≤1%（按 N 分母）”规则对齐。",
        "   - 在结论页中，差值单元格按以下规则着色：",
        "       <1% → 灰色；1%~2% → 黄色；≥2% → 绿色。",
        "",
        "6) 方向比较限制（脚本实现细节）",
        "   - 方向分为两组：直角组 = {Left, Up, Right, Down}；斜角组 = {Up-Left, Up-Right, Down-Right, Down-Left}。",
        "   - 仅在组内做两两比较，不跨组比较。",
        "",
        "7) 概率统计表（概率统计页）",
        "   - 每个类别的概率由原始计数除以 Total 得到：Door_X = Door_X_count / Total；Dir_Y = Dir_Y_count / Total。",
        "",
        "8) 均值/方差/标准差（均值偏差页）",
        "   - 组内均值（例如门组）: mean = mean(p_i)（忽略为 0 的项以避免 Total=0 的影响）。",
        "   - 以百分比形式计算偏差列： (p_i - mean) * 100。",
        "   - 方差（%^2）使用样本方差（ddof=0），标准差为方差的平方根（%）。",
        ""
    ]
    if sheet_type == "ci":
        extra = [
            "本页（置信区间验证）中特别说明：",
            " - Doors 使用的 alpha = 0.05 / 4（Bonferroni 分配用于单个类别的 Wilson 区间计算）。",
            " - Directions 使用的 alpha = 0.05 / 8（Bonferroni 分配用于单个方向的 Wilson 区间计算）。",
            ""
        ]
    elif sheet_type == "doors_summary":
        extra = [
            "本页（结论-门）说明：",
            " - 对每个实验，门组内共有 4 个类别，共 T = C(4,2) = 6 个两两比较。",
            " - 使用 overall_alpha = 0.05，组内 Bonferroni 校正后 alpha_per_test = 0.05 / 6 ≈ 0.008333。",
            " - 每条结论为单侧精确二项检验显著的比较，格式： 实验编号 | 结论 | p_value | A_count | B_count | 差值(pA-pB, N分母)。",
            ""
        ]
    elif sheet_type == "dirs_summary":
        extra = [
            "本页（结论-方向）说明：",
            " - 方向被分为两组：直角组（4 个）与斜角组（4 个），每组内分别做两两比较。",
            " - 每组内比较数量均为 T = C(4,2) = 6，组内 Bonferroni 校正 alpha_per_test = 0.05 / 6。",
            " - 仅在组内记录显著结论，格式同上： 实验编号 | 结论 | p_value | A_count | B_count | 差值(pA-pB, N分母)。",
            ""
        ]
    else:
        extra = []
    lines = common_lines + extra
    text = "\n".join(lines)
    start_row = len(lines) + 3
    end_row = start_row - 1
    last_col = max_merge_cols
    merged_fmt = workbook.add_format({'text_wrap': True, 'valign': 'top'})
    worksheet.merge_range(0, 0, end_row, last_col, text, merged_fmt)
    worksheet.set_column(0, last_col, 40)
    for r in range(0, end_row + 1):
        worksheet.set_row(r, 18)
    return start_row

def process_dat_in_current_dir():
    for dat_file in glob.glob("*.dat"):
        base_name = os.path.splitext(os.path.basename(dat_file))[0]
        out_file = f"{base_name}.xlsx"
        if os.path.exists(out_file):
            continue
        with open(dat_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        sorted_ids = sorted(data.keys(), key=sort_key)
        rows = []
        for exp_id in sorted_ids:
            exp = data[exp_id]
            row = {"ID": exp_id}
            for k in door_keys:
                row[f"Door_{k}"] = exp["Doors"].get(k, 0)
            row["Total"] = exp.get("Total", 0)
            for k in direction_keys:
                row[f"Dir_{k.replace('-', '_')}"] = exp["Directions"].get(k, 0)
            rows.append(row)
        df_data = pd.DataFrame(rows)
        df_prob = df_data.copy()
        totals = df_data["Total"].replace(0, np.nan)
        for k in door_keys:
            df_prob[f"Door_{k}"] = df_data[f"Door_{k}"] / totals
        for k in direction_keys:
            df_prob[f"Dir_{k.replace('-', '_')}"] = df_data[f"Dir_{k.replace('-', '_')}"] / totals
        df_prob[[f"Door_{k}" for k in door_keys] + dir_cols] = df_prob[[f"Door_{k}" for k in door_keys] + dir_cols].fillna(0)
        df_norm = pd.DataFrame()
        df_norm["ID"] = df_prob["ID"]
        door_cols = [f"Door_{k}" for k in door_keys]
        door_probs_nonzero = df_prob[door_cols].replace(0, np.nan)
        df_norm["Door_mean"] = door_probs_nonzero.mean(axis=1, skipna=True).fillna(0)
        for k in door_keys:
            col = f"Door_{k}"
            df_norm[f"{col}(%)"] = (df_prob[col] - df_norm["Door_mean"]) * 100
        df_norm["Door_var(%^2)"] = door_probs_nonzero.mul(100).var(axis=1, ddof=0, skipna=True).fillna(0)
        df_norm["Door_std(%)"] = np.sqrt(df_norm["Door_var(%^2)"])
        dir_straight = [f"Dir_{k.replace('-', '_')}" for k in ["Left","Up","Right","Down"]]
        dir_straight_nonzero = df_prob[dir_straight].replace(0, np.nan)
        df_norm["Dir_straight_mean"] = dir_straight_nonzero.mean(axis=1, skipna=True).fillna(0)
        for col in dir_straight:
            df_norm[f"{col}(%)"] = (df_prob[col] - df_norm["Dir_straight_mean"]) * 100
        df_norm["Dir_straight_var(%^2)"] = dir_straight_nonzero.mul(100).var(axis=1, ddof=0, skipna=True).fillna(0)
        df_norm["Dir_straight_std(%)"] = np.sqrt(df_norm["Dir_straight_var(%^2)"])
        diag_keys = ["Up-Left","Up-Right","Down-Right","Down-Left"]
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
            + [f"Door_{k}(%)" for k in door_keys]
            + ["Door_var(%^2)", "Door_std(%)",
            "Dir_straight_mean"]
            + [f"Dir_{k}(%)" for k in ["Left","Up","Right","Down"]]
            + ["Dir_straight_var(%^2)", "Dir_straight_std(%)",
            "Dir_diagonal_mean"]
            + [f"Dir_{k.replace('-', '_')}(%)" for k in ["Up-Left","Up-Right","Down-Right","Down-Left"]]
            + ["Dir_diagonal_var(%^2)", "Dir_diagonal_std(%)",
            "Dir_combined_std(%)"]
        )
        ordered_cols = [c for c in ordered_cols if c in df_norm.columns]
        df_norm = df_norm[ordered_cols]
        with pd.ExcelWriter(out_file, engine="xlsxwriter") as writer:
            df_data.to_excel(writer, sheet_name="实验数据", index=False)
            df_prob.to_excel(writer, sheet_name="概率统计", index=False)
            df_norm.to_excel(writer, sheet_name="均值偏差(%)方差", index=False)
            workbook = writer.book
            worksheet_norm = writer.sheets["均值偏差(%)方差"]
            mean_fmt = workbook.add_format({'bg_color': '#FFF2CC'})
            var_fmt  = workbook.add_format({'bg_color': '#FCE4D6'})
            std_fmt  = workbook.add_format({'bg_color': '#E2EFDA'})
            highlight_means = [c for c in ["Door_mean", "Dir_straight_mean", "Dir_diagonal_mean"] if c in df_norm.columns]
            highlight_vars  = [c for c in ["Door_var(%^2)", "Dir_straight_var(%^2)", "Dir_diagonal_var(%^2)"] if c in df_norm.columns]
            highlight_stds  = [c for c in ["Door_std(%)", "Dir_straight_std(%)", "Dir_diagonal_std(%)", "Dir_combined_std(%)"] if c in df_norm.columns]
            item_diff_fmt = workbook.add_format({'bg_color': '#D9EAF7'})
            item_diff_cols = [c for c in df_norm.columns if c.endswith("(%)") and c not in highlight_stds]
            for col_name in highlight_means:
                col_idx = df_norm.columns.get_loc(col_name)
                worksheet_norm.set_column(col_idx, col_idx, None, mean_fmt)
            for col_name in highlight_vars:
                col_idx = df_norm.columns.get_loc(col_name)
                worksheet_norm.set_column(col_idx, col_idx, None, var_fmt)
            for col_name in highlight_stds:
                col_idx = df_norm.columns.get_loc(col_name)
                worksheet_norm.set_column(col_idx, col_idx, None, std_fmt)
            for col_name in item_diff_cols:
                col_idx = df_norm.columns.get_loc(col_name)
                worksheet_norm.set_column(col_idx, col_idx, None, item_diff_fmt)
            worksheet_doors = workbook.add_worksheet("门概率图")
            writer.sheets["门概率图"] = worksheet_doors
            groups = {}
            for exp_id in sorted_ids:
                m = re.match(r"(\d+)", exp_id)
                num = m.group(1) if m else exp_id
                groups.setdefault(num, []).append(exp_id)
            row_height_unit = 10
            col_width_unit = 3
            group_index = 0
            for num, exp_ids in groups.items():
                r = group_index * row_height_unit
                for j, exp_id in enumerate(exp_ids):
                    row = df_prob.loc[df_prob["ID"] == exp_id]
                    door_probs = {}
                    for k in door_keys:
                        col = f"Door_{k}"
                        door_probs[k] = (row.iloc[0][col] if not row.empty and col in row.columns else 0.0)
                    door_probs_for_plot = {
                        "Left": door_probs["Left"],
                        "Up": door_probs["Up"],
                        "Right": door_probs["Right"],
                        "Down": door_probs["Down"]
                    }
                    buf = plot_doors(exp_id, door_probs_for_plot)
                    c = j * col_width_unit
                    worksheet_doors.insert_image(r, c, f"{exp_id}_doors.png", {"image_data": buf})
                group_index += 1
            worksheet_dirs = workbook.add_worksheet("方向图")
            writer.sheets["方向图"] = worksheet_dirs
            groups = {}
            for exp_id in sorted_ids:
                m = re.match(r"(\d+)", exp_id)
                num = m.group(1) if m else exp_id
                groups.setdefault(num, []).append(exp_id)
            row_offset = 0
            for num, exp_ids in groups.items():
                col_offset = 0
                for exp_id in exp_ids:
                    row = df_prob.loc[df_prob["ID"] == exp_id]
                    probs = {}
                    for col in dir_cols:
                        probs[col] = (row.iloc[0][col] if not row.empty and col in row.columns else 0.0)
                    buf = plot_grid(exp_id, probs)
                    worksheet_dirs.insert_image(row_offset, col_offset, exp_id + ".png", {"image_data": buf})
                    col_offset += 5
                row_offset += 18
            worksheet_ci = workbook.add_worksheet("置信区间验证")
            writer.sheets["置信区间验证"] = worksheet_ci
            start_row_ci = write_formula_block_merged(worksheet_ci, sheet_type="ci", workbook=workbook, max_merge_cols=5)
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#DCE6F1'})
            small_col_width = 12
            worksheet_ci.set_column(0, 0, 18)
            worksheet_ci.set_column(1, 1, small_col_width)
            worksheet_ci.set_column(2, 6, 14)
            row_offset = start_row_ci
            for exp_id in sorted_ids:
                exp = data[exp_id]
                N = exp.get("Total", 0)
                alpha_doors = 0.05 / 4
                door_counts = {k: exp["Doors"].get(k, 0) for k in door_keys}
                door_results = verify_confidence(N, door_counts, alpha_doors)
                worksheet_ci.write(row_offset, 0, f"实验 {exp_id} - Doors", header_fmt)
                row_offset += 1
                headers = ["类别","频数","估计概率","下界","上界","误差幅度","≤1%"]
                worksheet_ci.write_row(row_offset, 0, headers, header_fmt)
                row_offset += 1
                for r in door_results:
                    worksheet_ci.write_row(row_offset, 0, [r[h] for h in headers])
                    row_offset += 1
                row_offset += 1
                alpha_dirs = 0.05 / 8
                dir_counts = {k: exp["Directions"].get(k, 0) for k in direction_keys}
                dir_results = verify_confidence(N, dir_counts, alpha_dirs)
                worksheet_ci.write(row_offset, 0, f"实验 {exp_id} - Directions", header_fmt)
                row_offset += 1
                worksheet_ci.write_row(row_offset, 0, headers, header_fmt)
                row_offset += 1
                for r in dir_results:
                    worksheet_ci.write_row(row_offset, 0, [r[h] for h in headers])
                    row_offset += 1
                row_offset += 2
            worksheet_summary_doors = workbook.add_worksheet("结论-门")
            writer.sheets["结论-门"] = worksheet_summary_doors
            worksheet_summary_dirs = workbook.add_worksheet("结论-方向")
            writer.sheets["结论-方向"] = worksheet_summary_dirs
            start_row_doors = write_formula_block_merged(worksheet_summary_doors, sheet_type="doors_summary", workbook=workbook, max_merge_cols=5)
            start_row_dirs = write_formula_block_merged(worksheet_summary_dirs, sheet_type="dirs_summary", workbook=workbook, max_merge_cols=5)
            header_row = ["实验编号", "结论", "p_value", "A_count", "B_count", "差值(pA-pB, N分母)"]
            worksheet_summary_doors.set_column(0, 0, 14)
            worksheet_summary_doors.set_column(1, 1, 18)
            worksheet_summary_doors.set_column(2, 5, 12)
            worksheet_summary_dirs.set_column(0, 0, 14)
            worksheet_summary_dirs.set_column(1, 1, 18)
            worksheet_summary_dirs.set_column(2, 5, 12)
            worksheet_summary_doors.write_row(start_row_doors, 0, header_row, header_fmt)
            worksheet_summary_dirs.write_row(start_row_dirs, 0, header_row, header_fmt)
            row_d = start_row_doors + 1
            row_dir = start_row_dirs + 1
            for exp_id in sorted_ids:
                exp = data[exp_id]
                N = exp.get("Total", 0)
                door_counts = {k: exp["Doors"].get(k, 0) for k in door_keys}
                door_conclusions = pairwise_significant_higher_group(door_counts, door_keys, overall_alpha=0.05)
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
                dir_counts = {k: exp["Directions"].get(k, 0) for k in direction_keys}
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
            fmt_gray = workbook.add_format({'bg_color': '#D9D9D9'})
            fmt_yellow = workbook.add_format({'bg_color': '#FFD966'})
            fmt_green = workbook.add_format({'bg_color': '#A9D08E'})
            diff_col_idx = 5
            row_d_end = row_d - 1
            if row_d_end >= start_row_doors + 1:
                worksheet_summary_doors.conditional_format(start_row_doors + 1, diff_col_idx, row_d_end, diff_col_idx,
                    {'type': 'cell', 'criteria': '<', 'value': 0.01, 'format': fmt_gray})
                worksheet_summary_doors.conditional_format(start_row_doors + 1, diff_col_idx, row_d_end, diff_col_idx,
                    {'type': 'cell', 'criteria': 'between', 'minimum': 0.01, 'maximum': 0.02, 'format': fmt_yellow})
                worksheet_summary_doors.conditional_format(start_row_doors + 1, diff_col_idx, row_d_end, diff_col_idx,
                    {'type': 'cell', 'criteria': '>=', 'value': 0.02, 'format': fmt_green})
            row_dir_end = row_dir - 1
            if row_dir_end >= start_row_dirs + 1:
                worksheet_summary_dirs.conditional_format(start_row_dirs + 1, diff_col_idx, row_dir_end, diff_col_idx,
                    {'type': 'cell', 'criteria': '<', 'value': 0.01, 'format': fmt_gray})
                worksheet_summary_dirs.conditional_format(start_row_dirs + 1, diff_col_idx, row_dir_end, diff_col_idx,
                    {'type': 'cell', 'criteria': 'between', 'minimum': 0.01, 'maximum': 0.02, 'format': fmt_yellow})
                worksheet_summary_dirs.conditional_format(start_row_dirs + 1, diff_col_idx, row_dir_end, diff_col_idx,
                    {'type': 'cell', 'criteria': '>=', 'value': 0.02, 'format': fmt_green})
        print(f"{out_file} 已生成.")

BD_GROUPS = ["BD", "BDXL", "BDKp", "BDXLKp"]
BDI_GROUPS = ["BDI", "BDIXL", "BDIKp", "BDIXLKp"]
N_VALUES = [1,2,3,4,5,6,7]

def extract_version_from_name(name):
    m = re.search(r"(\d+\.\d+)w", name)
    if not m:
        return None
    try:
        return float(m.group(1))
    except:
        return None

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
                if sub.isdigit():
                    n = int(sub)
                    if n in N_VALUES:
                        bdi_detail[group][n].append(full)
    lines = []
    lines.append("| # | layers | rep(w) | rep+(w) |")
    lines.append("|:--:|:--:|:--:|:--:|")
    for g in BD_GROUPS:
        files = group_files.get(g, [])
        layers = len(files) if files else ""
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
        def summarize(lst):
            if not lst:
                return ""
            vals, counts = np.unique(np.array(lst), return_counts=True)
            mode = vals[np.argmax(counts)]
            return f"{mode:.2f}"
        rep_v = summarize(rep_versions)
        rplus_v = summarize(rplus_versions)
        lines.append(f"| {g} | {layers} | {rep_v} | {rplus_v} |")
    lines.append("")
    lines.append("| # | layers | N | c589 | c599 | t102 |rep(w) | rep+(w) |")
    lines.append("|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|")
    for g in BDI_GROUPS:
        files_all = group_files.get(g, [])
        layers = len(files_all) if files_all else ""
        first_row = True
        for n in N_VALUES:
            files_n = bdi_detail[g][n]
            def has_tag(tag):
                return any(tag.lower() in os.path.basename(f).lower() for f in files_n)
            c589 = 1 if has_tag("c589") else 0
            c599 = 1 if has_tag("c599") else 0
            t102 = 1 if has_tag("t102") else 0
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
            def summarize(lst):
                if not lst:
                    return ""
                vals, counts = np.unique(np.array(lst), return_counts=True)
                mode = vals[np.argmax(counts)]
                return f"{mode:.2f}"
            rep_v = summarize(rep_versions)
            rplus_v = summarize(rplus_versions)
            g_cell = g if first_row else ""
            layers_cell = layers if first_row else ""
            lines.append(
                f"| {g_cell} | {layers_cell} | {n} | {c589} | {c599} | {t102} | {rep_v} | {rplus_v} |"
            )
            first_row = False
    md_path = os.path.join(base_dir, "statistics.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("statistics.md 已生成:", md_path)
    return md_path

def process_all_dat_files(base_dir):
    base_dir = os.path.abspath(base_dir)
    created = []
    skipped = []
    for root, dirs, files in os.walk(base_dir):
        if not any(f.lower().endswith(".dat") for f in files):
            continue
        cwd = os.getcwd()
        try:
            os.chdir(root)
            before = set(glob.glob("*.xlsx"))
            process_dat_in_current_dir()
            after = set(glob.glob("*.xlsx"))
            new_files = after - before
            for x in new_files:
                created.append(os.path.join(root, x))
            for x in before:
                skipped.append(os.path.join(root, x))
        finally:
            os.chdir(cwd)
    md_path = generate_statistics_md(base_dir)
    return {"created": created, "skipped": skipped, "statistics_md": md_path}

if __name__ == "__main__":
    res = process_all_dat_files(os.getcwd())
    print("created:", len(res["created"]))
    print("skipped:", len(res["skipped"]))
    print("statistics_md:", res["statistics_md"])
