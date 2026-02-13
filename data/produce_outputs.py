#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
produce_output.py

提取每个 xlsx 中的“有效结论”（基于差值阈值），按大组/小组/类型汇总生成 summary xlsx。
差值以 Excel 原生百分比格式输出，四舍五入到整数百分位（0.5 向上）。
输出文件写入 ./summary 目录（不存在则创建）。
依赖: pandas, openpyxl, xlsxwriter
"""
import os
import re
from collections import defaultdict
import pandas as pd

# ---------- 配置 ----------
BASE_DIR = os.getcwd()
SUMMARY_DIR = os.path.join(BASE_DIR, "summary")
BD_GROUPS = ["BD", "BDXL", "BDKp", "BDXLKp"]
BDI_GROUPS = ["BDI", "BDIXL", "BDIKp", "BDIXLKp"]
SUBGROUPS = list(range(0, 8))  # 0..7

SHEET_DOORS = "结论-门"
SHEET_DIRS = "结论-方向"

PREFIX_RPLUS = "r+"
PREFIX_REP = "rep"

# 差值阈值（修改此值以改变判定标准）
DIFF_THRESHOLD = 0.02

# ---------- 辅助函数 ----------
def detect_file_group_subgroup(xlsx_path):
    """
    根据文件路径判断所属大组、子组编号（0..7）和类型('r+'/'rep')。
    规则：顶层 BD/BDXL/BDKp/BDXLKp 对应 subgroup 0；
    顶层为 BDI/BDIXL/BDIKp/BDIXLKp 且下一级为数字 1..7 则对应 subgroup 1..7。
    """
    rel = os.path.relpath(xlsx_path, BASE_DIR)
    parts = rel.split(os.sep)
    top = parts[0] if parts else ""
    for i, big in enumerate(BD_GROUPS):
        bdi_variant = BDI_GROUPS[i]
        if top == big:
            subgroup = 0
            name = os.path.basename(xlsx_path).lower()
            typ = "r+" if name.startswith(PREFIX_RPLUS) else ("rep" if name.startswith(PREFIX_REP) else None)
            return big, subgroup, typ
        if top == bdi_variant:
            if len(parts) >= 2:
                try:
                    n = int(parts[1])
                    if 1 <= n <= 7:
                        name = os.path.basename(xlsx_path).lower()
                        typ = "r+" if name.startswith(PREFIX_RPLUS) else ("rep" if name.startswith(PREFIX_REP) else None)
                        return big, n, typ
                except Exception:
                    pass
    return None, None, None

def row_has_zero_numeric_series(series):
    """
    判断 pandas Series 中是否存在数值型且等于 0 的元素（忽略 NaN 与非数值）。
    """
    nums = pd.to_numeric(series, errors='coerce')
    return ((nums == 0).any())

def extract_effective_from_xlsx(path_xlsx, diff_threshold=DIFF_THRESHOLD):
    """
    从单个 xlsx 提取有效结论（基于差值阈值）：
    返回 dict: {"doors": [(id, concl, diff), ...], "dirs": [...]}
    规则：
      - 读取对应 sheet（若不存在则跳过）
      - 取最后一列为差值列，若该列数值 >= diff_threshold 且该行没有数值 0，则为有效
      - 取前两列作为 ID 与 结论文本
    """
    res = {"doors": [], "dirs": []}
    try:
        xls = pd.ExcelFile(path_xlsx, engine="openpyxl")
    except Exception:
        return res

    for sheet_name, key in ((SHEET_DOORS, "doors"), (SHEET_DIRS, "dirs")):
        if sheet_name not in xls.sheet_names:
            continue
        try:
            df = pd.read_excel(xls, sheet_name=sheet_name, engine="openpyxl")
        except Exception:
            continue
        if df.shape[1] < 1:
            continue
        diff_col = df.columns[-1]
        for idx, row in df.iterrows():
            diff_val = pd.to_numeric(row[diff_col], errors='coerce')
            if pd.isna(diff_val):
                continue
            if diff_val < diff_threshold:
                continue
            if row_has_zero_numeric_series(row):
                continue
            id_val = row.iloc[0] if df.shape[1] >= 1 else ""
            concl_val = row.iloc[1] if df.shape[1] >= 2 else ""
            res[key].append((str(id_val) if not pd.isna(id_val) else "", str(concl_val) if not pd.isna(concl_val) else "", float(diff_val)))
    return res

def collect_all_effective(base_dir):
    """
    遍历 base_dir，收集所有 xlsx 的有效结论，按 big_group / type / subgroup 存储。
    结构:
      data[big_group][type_str]['doors' or 'dirs'][subgroup] -> dict key=(id,concl) -> diff
    """
    data = {}
    for big in BD_GROUPS:
        data[big] = {"r+": {"doors": defaultdict(dict), "dirs": defaultdict(dict)},
                     "rep": {"doors": defaultdict(dict), "dirs": defaultdict(dict)}}

    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if not f.lower().endswith(".xlsx"):
                continue
            full = os.path.join(root, f)
            big, subgroup, typ = detect_file_group_subgroup(full)
            if big is None or subgroup is None or typ is None:
                continue
            eff = extract_effective_from_xlsx(full, DIFF_THRESHOLD)
            for key in ("doors", "dirs"):
                for (idv, concl, diff) in eff.get(key, []):
                    data[big][typ][key][subgroup][(idv, concl)] = diff
    return data

# ---------- 百分比处理（返回数值型，便于 Excel 原生格式） ----------
def round_to_nearest_percent_value(diff_value):
    """
    将 0..1 的 diff_value 四舍五入到最近的百分位并返回数值（例如 0.023 -> 0.02）。
    使用 0.5 向上规则：实现为 int(diff*100 + 0.5)/100
    返回 None 表示无效输入。
    """
    try:
        v = float(diff_value)
    except Exception:
        return None
    pct_int = int(v * 100 + 0.5)
    return pct_int / 100.0  # 返回数值，例如 0.02

def build_sheet_dataframe(entries_by_subgroup):
    """
    entries_by_subgroup: dict subgroup -> dict key=(id,concl) -> diff
    返回 DataFrame，列: ['ID','结论','0','1',...,'7']
    值为数值型（0.02 表示 2%），无值则为 NaN
    """
    all_keys = set()
    for sg, d in entries_by_subgroup.items():
        all_keys.update(d.keys())
    def key_sort(k):
        try:
            m = re.match(r"(\d+)", k[0])
            if m:
                return (int(m.group(1)), k[0], k[1])
        except Exception:
            pass
        return (k[0], k[1])
    all_keys = sorted(all_keys, key=key_sort)
    rows = []
    for k in all_keys:
        row = {"ID": k[0], "结论": k[1]}
        for sg in SUBGROUPS:
            raw = entries_by_subgroup.get(sg, {}).get(k, None)
            if raw is None or raw == "":
                row[str(sg)] = float("nan")
            else:
                rounded = round_to_nearest_percent_value(raw)
                row[str(sg)] = rounded if rounded is not None else float("nan")
        rows.append(row)
    cols = ["ID", "结论"] + [str(s) for s in SUBGROUPS]
    df = pd.DataFrame(rows, columns=cols)
    return df

def write_group_summary_xlsx(big_group, group_data, out_dir):
    """
    将每个大组的 summary 写入 out_dir 下的 {big_group}_summary.xlsx
    包含四张 sheet: r+_门, rep_门, r+_方向, rep_方向
    差值列使用 Excel 原生百分比格式（num_format '0%').
    """
    if not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    out_name = f"{big_group}_summary.xlsx"
    out_path = os.path.join(out_dir, out_name)
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        workbook = writer.book
        pct_format = workbook.add_format({'num_format': '0%'})
        for typ in ("r+", "rep"):
            for key, sheet_suffix in (("doors", "门"), ("dirs", "方向")):
                entries_by_subgroup = group_data[typ][key]
                df = build_sheet_dataframe(entries_by_subgroup)
                sheet_name = f"{typ}_{sheet_suffix}"
                if len(sheet_name) > 31:
                    sheet_name = sheet_name[:31]
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                worksheet = writer.sheets[sheet_name]
                # 第一两列为 ID, 结论；后面 8 列为 0..7 -> 需要设置为百分比格式
                # set_column(col_first, col_last, width, format)
                # 列索引从 0 开始，0->A,1->B,2->C ... 2..9 对应 C..J
                try:
                    worksheet.set_column(2, 9, None, pct_format)
                except Exception:
                    # 若列数不足（没有任何数据列），忽略
                    pass
    return out_path

# ---------- 主流程 ----------
def main():
    print("Scanning .xlsx files and extracting effective conclusions with DIFF_THRESHOLD =", DIFF_THRESHOLD)
    data = collect_all_effective(BASE_DIR)
    out_files = []
    for big in BD_GROUPS:
        out = write_group_summary_xlsx(big, data[big], SUMMARY_DIR)
        out_files.append(out)
        print("Wrote:", out)
    print("Done. Generated:", ", ".join(out_files))

if __name__ == "__main__":
    main()
