# data 目录说明

本目录是实验数据处理与网页输出目录，核心流程为：

1. 读取各数据目录中的 dat 文件。
2. 由 BD.py 生成对应 xlsx。
3. 从 xlsx 提取有效结论并生成 summary xlsx。
4. 将 xlsx 批量导出为 html，并生成 index.html 导航页。

## 快速使用

在本目录执行：

python vba.py

该命令会自动完成以下步骤：

1. 按配置决定是否先清理旧文件。
2. 调用 BD.py 处理 dat 并生成 xlsx（缺失时创建）。
3. 调用 produce_outputs.py 生成 summary 下的结论汇总 xlsx。
4. 通过 Excel VBA 将 xlsx 导出为 html，并刷新 index.html。
5. 若 math/math.html 存在，则在 index.html 顶部加入“数据说明”链接。

## FORCE_UPDATE 配置说明

配置位置：vba.py 顶部。

1. FORCE_UPDATE = False（增量模式）
仅在目标 html 不存在时导出，适合日常快速更新。

2. FORCE_UPDATE = True（全量重建模式）
先清理数据目录中的旧过程文件，再重建。
当前清理范围仅限以下数据目录及其子目录：

- BD
- BDI
- BDIKp
- BDIXL
- BDIXLKp
- BDKp
- BDXL
- BDXLKp

清理规则：

- 保留 .dat
- 删除其他文件（包括 .xlsx、.html）
- 删除 Excel 导出伴生目录（*.files）

说明：根目录脚本、summary、__pycache__ 等非数据目录不会被清理。

## 各脚本作用

1. vba.py
主入口脚本。负责串联清理、dat 转 xlsx、结论汇总、xlsx 转 html、生成 index.html，并在首页顶部加入“数据说明”入口（若 math/math.html 存在）。

2. produce_outputs.py
从各 xlsx 的结论 sheet 中提取有效结论，按大组输出 summary xlsx。

3. path.py
为 vba.py 提供数据根目录配置：

TARGET_PATH = r"你的 data 目录绝对路径"

4. tree.py
扫描目录结构并生成 tree.md。

## 主要输出文件

1. statistics.md
数据统计概览（由 BD.py 生成/更新）。

2. summary/*.xlsx
有效结论汇总文件（由 produce_outputs.py 生成）。

3. 各数据目录下 *.html 与 *.files
由 xlsx 导出的网页及伴生资源。

4. index.html
总览导航页，顶部可显示“数据说明”链接，随后包含统计表与各 html 链接。

## 运行环境

1. Windows + 已安装 Microsoft Excel（用于 COM 自动化导出 html）。
2. Python 依赖建议至少包含：pandas、openpyxl、xlsxwriter、pywin32。
