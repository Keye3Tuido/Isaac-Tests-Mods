# 头目方向统计模组说明

本仓库用于收集并分析以撒相关头目方向实验数据，支持多种条件组合（合层、刀柄、指定物品等），并提供从 dat 到 Excel 再到网页的完整输出链路。

## 仓库结构

1. BossDirection* 与 BossDirectionItems* 目录
游戏侧统计模组源码与相关内容。

2. BD.py
数据分析核心脚本。负责将 dat 实验数据转换为 xlsx，并输出统计结果（含概率表、图表、结论 sheet、statistics.md）。

3. data 目录
数据处理工作区与网页发布目录。
常用入口是 data/vba.py，用于自动串联整个产出流程。

## 模组用途总览

1. BossDirection
统计各楼层最终头目房方向，以及初始房间四门中哪一门更接近最终头目。

2. BossDirectionXL
统计合层时首个头目房（虚空层取精神错乱房间）方向与更优前进门。

3. BossDirectionKp
统计拥有刀柄时（4c/4d）最终头目方向与更优前进门。

4. BossDirectionXLKp
统计合层且拥有刀柄时（3c/3d）首个头目方向与更优前进门。

5. BossDirectionItems
统计携带指定物品时的最终头目方向与更优前进门。

6. BossDirectionItemsXL
统计合层且携带指定物品时的首个头目方向与更优前进门。

7. BossDirectionItemsKp
统计携带指定物品且拥有刀柄时（4c/4d）的方向与更优前进门。

8. BossDirectionItemsXLKp
统计合层、携带指定物品且拥有刀柄时（3c/3d）的方向与更优前进门。

## 数据处理流程（推荐）

在 data 目录执行：

python vba.py

流程说明：

1. 可选强制清理旧过程文件（由 FORCE_UPDATE 控制）。
2. 调用 BD.py：dat 转 xlsx，并更新 statistics.md。
3. 调用 produce_outputs.py：生成 summary 结论汇总 xlsx。
4. 调用 Excel VBA：将 xlsx 批量导出为 html，刷新 index.html。
5. index.html 顶部会优先加入指向 data/math/math.html 的“数据说明”链接（文件存在时显示）。

## 输出结果

1. data/statistics.md
数据统计摘要。

2. data/summary/*.xlsx
有效结论汇总。

3. data 下各数据目录中的 *.html 及 *.files
实验结果网页及资源文件。

4. data/index.html
网页总导航入口，顶部优先显示“数据说明”链接，并汇总统计表、各实验结果页与结论页链接。

## 环境要求

1. Windows。
2. Microsoft Excel（用于 COM 自动化导出 html）。
3. Python 常用依赖：pandas、openpyxl、xlsxwriter、pywin32、numpy、scipy、matplotlib。
