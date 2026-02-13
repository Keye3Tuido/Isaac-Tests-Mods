#!/usr/bin/env python3
import os

IGNORE = {".git", "node_modules", ".idea", ".vscode"}


def contains_xlsx(path):
    """判断目录是否包含 xlsx 文件（递归）"""
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.lower().endswith(".xlsx"):
                return True
    return False


def generate_tree(path, prefix=""):
    entries = sorted(os.listdir(path))
    entries = [e for e in entries if e not in IGNORE]

    tree_lines = []
    for i, entry in enumerate(entries):
        full_path = os.path.join(path, entry)
        connector = "├── " if i < len(entries) - 1 else "└── "
        tree_lines.append(prefix + connector + entry)

        if os.path.isdir(full_path):
            # 判断是否需要继续展开
            if contains_xlsx(full_path):
                # 继续完整展开
                extension = "│   " if i < len(entries) - 1 else "    "
                tree_lines.extend(generate_tree(full_path, prefix + extension))
            else:
                # 不展开，但显示一层省略号
                extension = "│   " if i < len(entries) - 1 else "    "
                tree_lines.append(prefix + extension + "└── ...")

    return tree_lines


if __name__ == "__main__":
    root = "."
    lines = ["# 目录树", ""]
    lines.extend(generate_tree(root))
    lines.append("")  # 文件末尾空行

    with open("tree.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("目录树已生成：tree.md")
