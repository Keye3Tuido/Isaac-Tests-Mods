# 数据处理数学说明（误差 1%，置信度 99.9%）

## 1. 目标与符号定义

设：

- $p$：某事件真实概率
- $\hat p$：样本频率（样本概率）
- $n$：样本量
- $\varepsilon$：允许误差上限
- $CL$：置信度（confidence level）
- $\alpha = 1-CL$：显著性水平（双侧区间总尾概率）

本项目取：

- 误差上限 $\varepsilon = 0.01$（即 $1\%$）
- 置信度 $CL = 0.999$（即 $99.9\%$）

---

## 2. 样本量下限的理论依据

采用伯努利比例估计的正态近似（中心极限定理 / 二项分布正态近似）：

$$
\hat p \approx \mathcal N\!\left(p,\ \frac{p(1-p)}{n}\right)
$$

双侧误差控制关系：

$$
\Pr\!\left(\left|\hat p-p\right|\le z_{1-\alpha/2}\sqrt{\frac{p(1-p)}{n}}\right)\approx 1-\alpha
$$

若要求误差不超过 $\varepsilon$，需满足：

$$
z_{1-\alpha/2}\sqrt{\frac{p(1-p)}{n}} \le \varepsilon
\quad\Longrightarrow\quad
n \ge \frac{z_{1-\alpha/2}^2\,p(1-p)}{\varepsilon^2}
$$

---

## 3. 最保守上界与统一样本量公式

因为 $p(1-p)$ 在 $p=0.5$ 时取最大值 $0.25$，故有：

$$
p(1-p)\le \frac14
$$

得到统一保守下界：

$$
n \ge \frac{z_{1-\alpha/2}^2}{4\varepsilon^2}
$$

---

## 4. 数值代入（99.9%，1%）

### 4.1 参数来源（首次出现数字的来源）

- $0.01$：来自“误差不超过 $1\%$”
- $0.999$：来自“置信度 $99.9\%$”
- $\alpha = 1-0.999 = 0.001$
- $\alpha/2 = 0.0005$（双侧每侧尾概率）
- $\frac14$：来自最保守情形 $p=0.5$ 的 $p(1-p)$ 最大值

### 4.2 计算

$$
z_{1-\alpha/2} = z_{0.9995} \approx 3.290526731
$$

$$
n_{\min}
=
\left\lceil
\frac{z^2}{4\times 0.01^2}
\right\rceil
=
\left\lceil
\frac{3.290526731^2}{0.0004}
\right\rceil
=
\left\lceil
27068.9154
\right\rceil
=
27069
$$

结论：在“误差 $\le 1\%$、置信度 $99.9\%$”下，基础样本量为 **27069**。

---

## 5. 与项目样本量关系

若每组样本量取 $30000$，则：

$$
30000 > 27069
$$

因此该样本量高于理论基础下限。

---

## 6. 概率估计口径

对任一类别（门或方向）：

- 记该类别观测计数为 $A$
- 记该实验总样本量为 $N$

则类别概率估计为：

$$
\hat p = \frac{A}{N}
$$

在两类比较（$A$ 类 vs $B$ 类）中，常定义条件样本量：

$$
m=A+B
$$

对应条件概率可写为：

$$
\hat p_A^{(\text{cond})}=\frac{A}{m}
$$

---

## 7. 组内均值、偏差、方差、标准差

### 7.1 分组定义（方向分组）

方向被拆成两组，分别计算：

- 直角组：$\{\text{Left, Up, Right, Down}\}$（4 类）
- 斜角组：$\{\text{Up-Left, Up-Right, Down-Right, Down-Left}\}$（4 类）

门方向单独作为门组（4 类）。

### 7.2 组内均值与偏差

对某组内概率 $\{p_1,\dots,p_k\}$（这里 $k=4$），组内均值：

$$
\bar p=\frac{1}{k}\sum_{i=1}^k p_i
$$

偏差百分比列：

$$
\Delta_i(\%) = (p_i-\bar p)\times 100
$$

### 7.3 方差与标准差（修正口径）

方差采用 **总体方差口径**（`ddof=0`）：

$$
\mathrm{Var}_{\%^2}
=
\frac{1}{k}\sum_{i=1}^k \left(100p_i-100\bar p\right)^2
$$

标准差为：

$$
\mathrm{Std}_{\%}=\sqrt{\mathrm{Var}_{\%^2}}
$$

说明：`ddof=0` 对应总体方差，不是样本方差（样本方差应是 `ddof=1`）。

---

## 8. Wilson 置信区间验证

对每个类别，给定 $A,N,\alpha$，先算：

$$
z=\Phi^{-1}(1-\alpha/2),\quad \hat p=\frac{A}{N}
$$

Wilson 区间：

$$
\mathrm{denom}=1+\frac{z^2}{N}
$$

$$
\mathrm{center}=\hat p+\frac{z^2}{2N}
$$

$$
\mathrm{rad}=z\sqrt{\frac{\hat p(1-\hat p)}{N}+\frac{z^2}{4N^2}}
$$

$$
\mathrm{lower}=\frac{\mathrm{center}-\mathrm{rad}}{\mathrm{denom}},\quad
\mathrm{upper}=\frac{\mathrm{center}+\mathrm{rad}}{\mathrm{denom}}
$$

并截断到 $[0,1]$。

误差幅度定义为：

$$
\mathrm{margin}=\max(\hat p-\mathrm{lower},\ \mathrm{upper}-\hat p)
$$

验证项“$\le 1\%$”即判断：

$$
\mathrm{margin}\le 0.01
$$

### 8.1 置信区间页的 $\alpha$ 取值

- 门组（4 类）：$\alpha_{\text{doors}}=0.05/4$
- 方向组（8 类）：$\alpha_{\text{dirs}}=0.05/8$

其中：

- $0.05$：区间验证使用的总体显著性水平
- $4,8$：分别来自门类别数、方向类别数（用于保守拆分）

---

## 9. 显著性检验与多重比较

### 9.1 两类比较模型

比较 $A$ 类与 $B$ 类时，令 $m=A+B$。
在原假设 $H_0:p_A=p_B$ 下，等价于：

$$
A\sim \mathrm{Binomial}(m,0.5)
$$

做单侧检验：

$$
H_1:p_A>0.5
$$

得到单侧 $p$ 值。

### 9.2 组内 Bonferroni 校正

若某组内可比类别数为 $k$，则两两比较总数：

$$
T=\binom{k}{2}
$$

校正后阈值：

$$
\alpha_{\text{per-test}}=\frac{0.05}{T}
$$

当且仅当：

$$
p\text{-value}\le \alpha_{\text{per-test}}
$$

才记录显著结论（如 $A>B$ 或 $B>A$）。

### 9.3 方向比较限制

方向比较仅在组内进行：

- 直角组内两两比较（$k=4,\ T=6$）
- 斜角组内两两比较（$k=4,\ T=6$）

不做跨组比较。

---

## 10. 差值与效应量展示

对显著对比项，差值定义为：

$$
\mathrm{diff}_{\text{total}}=\frac{A}{N}-\frac{B}{N}
$$

这里分母固定用该实验总样本量 $N$（不是 $m=A+B$），用于表达“在总样本尺度上的概率差”。

展示阈值：

- $\mathrm{diff}<0.01$：灰色
- $0.01\le \mathrm{diff}<0.02$：黄色
- $\mathrm{diff}\ge 0.02$：绿色

说明：该着色是展示规则，不等同于显著性判定规则；显著性仍由二项检验与 Bonferroni 校正给出。

---

## 11. 口径声明

本文的样本量与区间/检验说明属于“实验设计与统计推断口径”，核心基于：

1. 比例估计正态近似（大样本条件）
2. 最保守方差上界 $p(1-p)\le 1/4$
3. 组内多重比较控制（Bonferroni）
