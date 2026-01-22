# BD.py
import os, glob, json, re, io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from math import atan2, degrees, sqrt
from scipy.stats import norm, binomtest

BD_GROUPS = ["BD", "BDXL", "BDKp", "BDXLKp"]
BDI_GROUPS = ["BDI", "BDIXL", "BDIKp", "BDIXLKp"]
N_VALUES = [1,2,3,4,5,6,7]

DOOR_KEYS = ["Left","Up","Right","Down"]
DIRECTION_KEYS = ["Left","Up-Left","Up","Up-Right","Right","Down-Right","Down","Down-Left"]
DIR_COLS = [f"Dir_{k.replace('-', '_')}" for k in DIRECTION_KEYS]

def extract_version_from_name(name):
    m = re.search(r"(\d+\.\d+)w", name)
    if not m: return None
    try: return float(m.group(1))
    except: return None

def summarize_num(lst):
    if not lst: return None
    vals, counts = np.unique(np.array(lst), return_counts=True)
    return float(vals[np.argmax(counts)])

def _layers_from_group_files(files):
    counts = []
    for full in files:
        try:
            with open(full,"r",encoding="utf-8") as f:
                data = json.load(f)
            c = sum(1 for exp in data.values() if isinstance(exp,dict) and "Total" in exp)
            if c>0: counts.append(c)
        except: continue
    if not counts: return ""
    vals,freqs = np.unique(np.array(counts),return_counts=True)
    return str(int(vals[np.argmax(freqs)]))

def n_to_bits_t102_low(n):
    t102 = n & 1
    c599 = (n>>1) & 1
    c589 = (n>>2) & 1
    return (c589,c599,t102)

def generate_statistics_md(base_dir):
    base_dir = os.path.abspath(base_dir)
    group_files = {g:[] for g in BD_GROUPS+BDI_GROUPS}
    bdi_detail = {g:{n:[] for n in N_VALUES} for g in BDI_GROUPS}

    for root,dirs,files in os.walk(base_dir):
        for f in files:
            if not f.lower().endswith(".dat"): continue
            full = os.path.join(root,f)
            rel = os.path.relpath(full,base_dir)
            parts = rel.split(os.sep)
            if len(parts)<2: continue
            group = parts[0]
            if group not in group_files: continue
            group_files[group].append(full)
            if group in BDI_GROUPS and len(parts)>=2:
                sub = parts[1]
                if re.fullmatch(r"\d+",sub):
                    n=int(sub)
                    if n in N_VALUES: bdi_detail[group][n].append(full)

    lines=[]
    # 第一张表
    lines.append("| # | layers | rep(w) | rep+(w) |")
    lines.append("|:--:|:--:|:--:|:--:|")
    rep_sum_1=rplus_sum_1=0.0
    for g in BD_GROUPS:
        files=group_files.get(g,[])
        layers=_layers_from_group_files(files)
        rep_versions=[]; rplus_versions=[]
        for full in files:
            v=extract_version_from_name(os.path.basename(full))
            if v is None: continue
            lower=os.path.basename(full).lower()
            if "rep" in lower and "r+" not in lower: rep_versions.append(v)
            if "r+" in lower: rplus_versions.append(v)
        rep_v_num=summarize_num(rep_versions); rplus_v_num=summarize_num(rplus_versions)
        rep_v=f"{rep_v_num:.2f}" if rep_v_num is not None else ""
        rplus_v=f"{rplus_v_num:.2f}" if rplus_v_num is not None else ""
        if rep_v_num is not None: rep_sum_1+=rep_v_num
        if rplus_v_num is not None: rplus_sum_1+=rplus_v_num
        lines.append(f"| {g} | {layers} | {rep_v} | {rplus_v} |")
    lines.append(f"| Total |  | {rep_sum_1:.2f} | {rplus_sum_1:.2f} |")
    lines.append("")

    # 第二张表
    lines.append("| # | layers | N | c589 | c599 | t102 | rep(w) | rep+(w) |")
    lines.append("|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|")
    rep_sum_2=rplus_sum_2=0.0
    for g in BDI_GROUPS:
        files_all=group_files.get(g,[])
        layers=_layers_from_group_files(files_all)
        first_row=True
        for n in N_VALUES:
            n_str=str(n)
            files_n=bdi_detail[g][n]
            b_c589,b_c599,b_t102=n_to_bits_t102_low(n)
            rep_versions=[]; rplus_versions=[]
            for full in files_n:
                v=extract_version_from_name(os.path.basename(full))
                if v is None: continue
                lower=os.path.basename(full).lower()
                if "rep" in lower and "r+" not in lower: rep_versions.append(v)
                if "r+" in lower: rplus_versions.append(v)
            rep_v_num=summarize_num(rep_versions); rplus_v_num=summarize_num(rplus_versions)
            rep_v=f"{rep_v_num:.2f}" if rep_v_num is not None else ""
            rplus_v=f"{rplus_v_num:.2f}" if rplus_v_num is not None else ""
            if rep_v_num is not None: rep_sum_2+=rep_v_num
            if rplus_v_num is not None: rplus_sum_2+=rplus_v_num
            if first_row:
                g_cell=g; layers_cell=layers; first_row=False
            else:
                g_cell=""; layers_cell=""
            lines.append(f"| {g_cell} | {layers_cell} | {n_str} | {b_c589} | {b_c599} | {b_t102} | {rep_v} | {rplus_v} |")
    lines.append(f"| Total |  |  |  |  |  | {rep_sum_2:.2f} | {rplus_sum_2:.2f} |")

    md_path=os.path.join(base_dir,"statistics.md")
    with open(md_path,"w",encoding="utf-8") as f: f.write("\n".join(lines)+"\n")
    print("statistics.md 已生成:",md_path)
    return md_path

def process_dat_in_current_dir():
    # 这里保留你已有的 dat->xlsx 转换逻辑
    pass

def process_all_dat_files(base_dir):
    base_dir=os.path.abspath(base_dir)
    created=[]; skipped=[]
    for root,dirs,files in os.walk(base_dir):
        dat_files=[f for f in files if f.lower().endswith(".dat")]
        if not dat_files: continue
        cwd=os.getcwd()
        try:
            os.chdir(root)
            before=set(glob.glob("*.xlsx"))
            process_dat_in_current_dir()
            after=set(glob.glob("*.xlsx"))
            new_files=after-before
            for x in new_files: created.append(os.path.join(root,x))
            for x in before: skipped.append(os.path.join(root,x))
        finally: os.chdir(cwd)
    md_path=generate_statistics_md(base_dir)
    return {"created":created,"skipped":skipped,"statistics_md":md_path}

if __name__=="__main__":
    base=os.getcwd()
    res=process_all_dat_files(base)
    print("created:",len(res["created"]))
    print("skipped:",len(res["skipped"]))
    print("statistics_md:",res["statistics_md"])
