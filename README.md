# HighScoreCaptainCapri 📚

每日自动推送练习题到 Telegram，支持 LaTeX 渲染与自动判题。
全部跑在 GitHub Actions 上，不需要服务器。

当前主攻**模电 / 数电**，高数 / 大物的旧题库仍然并行可用。

## 两条出题通道

题目有两个来源，共用同一套渲染、推送和判题链路：

| 通道 | 位置 | 特点 |
| --- | --- | --- |
| **生成器** | `capri/` | 参数随机，题量无上限，标准答案是**算出来的**而不是录进去的 |
| **手录题库** | `problems/*.md` | 一题一文件，用来放生成器写不出来的题（看图判断那类） |

生成器的核心思路：一个参数化对象同时产出题面、图和标准答案，三者出自同一份数据，
所以不可能对不上。判题分三档强度 —— 语义等价（数电最强，形式无关）、
数值加误差传递、指标验证（设计题：验你的方案达不达标，而非比对标准答案）。

## 分支

| 分支 | 内容 |
| --- | --- |
| `main` | 当前主线，定时任务都从这里取代码 |
| `CapriACD` | 模电 / 数电的开发线，稳定后合回 `main` |
| `CapriMaPhy` | 2026-07-13 高数/大物考试前的完整快照，只读封存 |

> 定时触发的 workflow **永远从默认分支取代码**。在 `CapriACD` 上改了判题逻辑却没合回
> `main`，每天 8 点跑的还是旧代码 —— 这个坑踩过一次。

## 工作方式

- **每日推题**（`daily.yml`，北京时间 8:00）：抽 `DAILY_COUNT` 道题，
  其中 `GENERATED_COUNT` 道来自生成器，其余从 `problems/` 抽；
  静态题库不够就自动多生成几道补齐。每题渲染成一张 LaTeX 图片卡片推送。
- **自动判题**（`listener.yml`，每 2 小时拉起一次，处理积压的答案）：
  - 直接**回复**某道题的消息，内容写答案，机器人回复 ✅/❌；
  - 或发送 `/answer <题目ID> <答案>`；
  - 多空的题用 `;` 分隔，按题面顺序一次答完。

> 判题最多延迟 ~2 小时（Telegram 会保留未处理消息 24 小时，不会丢）。
> 想立刻出结果，手动 Run 一次 "Telegram Answer Bot"，
> 并把 `listen_seconds` 调大（默认 60 秒只够收积压，不够边答边判）。

两个 workflow 都支持手动触发时传参：

| Workflow | 参数 | 默认 |
| --- | --- | --- |
| Daily Problem Pusher | `daily_count` / `generated_count` | 10 / 3 |
| Telegram Answer Bot | `listen_seconds` | 60 |

## 判题器认什么写法

**逻辑表达式**（数电）：非号 `'` `~` `!` `/` `#` 和上划线都认，并置即与（`AB` 就是 `A·B`），
或用 `+` 或 `|`，异或用 `^` 或 `⊕`。把题头一起抄进来（`F(A,B,C) = AB+C`）会自动剥掉。
判定靠枚举 $2^n$ 行真值表，**与或式、或与式、带异或的形式一律等价即对**。
答错会指出具体哪一行对不上；逻辑对但没化到最简，会告诉你差几项几个字母。

**数值**：分数、`pi`、科学计数法、SI 词头和单位，如 `-14/15`、`2*pi`、`2e5`、
`2.2k`、`1.5kΩ`、`10μA`、`47pF`、`-3dB`。注意 `m`（毫）和 `M`（兆）**大小写敏感**。

## 添加手录题目

在 `problems/` 下新建一个 markdown 文件（文件名即题目 ID）：

```markdown
---
subject: 高数          # 或 大物 / 模电 / 数电
topic: Limits          # 知识点
weight: 5              # 抽中概率权重，默认 1
answer: -1/6           # 标准答案：数字、分数、pi 表达式或文本
tolerance: 0.01        # 可选：数值判题的相对误差，默认 0.01
disabled: true         # 可选：置 true 后不再进入每日抽取（见下方"埋葬题目"）
---
题目正文，支持行内公式 $\lim_{x \to 0}$ 与块级公式：

$$\int_0^{+\infty} x e^{-x}\,\mathrm{d}x$$

也支持插图：![图](./images/xxx.png)
```

### 埋葬题目

想让某道题（或某个学科的所有题）暂时不再被抽中，但又不想删掉文件，
在 frontmatter 里加一行 `disabled: true` 即可（`weight: 0` **不管用**——
权重会被 `select_daily` 强制拉到最低 1，所以 0 跟 1 效果一样）。
`disabled` 的题仍然会被 `load_problems` 读入，旧消息还能正常判题，
只是不会出现在新一天的抽取结果里。想重新启用就删掉这一行或改成 `false`。

## ⚠️ 已废弃 / 行为变化

引入生成器通道后，下面这些跟以前不一样了。**手录题库那条路全部照常工作**，
但有几个不对称的地方值得知道：

1. **题目 ID 可能带 `#`**。生成题的 ID 形如 `sop-simplify#0513499f`，
   `#` 后面是十六进制种子。用 `/answer` 时要**照抄完整的 ID**，
   只写 `sop-simplify` 找不到题。旧的纯 ID 仍然有效。

2. **`listen.py` 里的 `ID_TAG_RE` 已移除**，改用 `capri/core/session.py` 的
   `decode()` / `split_ref()`。老正则的字符集 `[A-Za-z0-9_-]` 装不下 `#`。

3. **手录题的答案不认 SI 词头**。`problem_bank.parse_number` 是老实现，
   `answer: 1.5k` 会被解析成 `1.5` 而不是 `1500`。生成题走的是新的
   `capri.core.quantity.parse`（认 k/M/μ/n/p、dB、Ω、中文单位）。
   手录模电题时要么把数值写全（`answer: 1500`），要么在题面里指定单位、答案存裸数。

4. **默认容差不一致**。手录题仍是 `problem_bank.DEFAULT_TOLERANCE = 0.01`；
   生成题的 `Numeric` 判题器默认 **0.05** —— 模电估算里 $r_{be}$ 取值、
   $\beta$ 取整、$U_{BE}$ 取 0.7 还是 0.6，不同解题路径差百分之几很正常。

5. **`select_daily` 不再是唯一的抽题入口**。现在由 `push.collect()` 编排：
   先向 `registry.draw_daily` 要 `GENERATED_COUNT` 道，剩下的名额才交给
   `select_daily`，静态题库空了会自动全用生成的。

6. **`render.render_problems` 的返回值键变了**：从 `problem.id` 变成"题目标识"，
   生成题是 `gid#seed`。落盘文件名会把 `#` 这类非法字符换成 `-`。

7. **README 里原来那句"每日推送高数/大物练习题"过期了**。2026-07-13 的考试已经结束，
   那批题现在是复习素材而不是主线；完整状态封存在 `CapriMaPhy` 分支。

## 本地调试

```bash
pip install -r requirements.txt
python -m playwright install chromium

python tests/test_capri.py                        # 跑测试（裸 assert，不需要 pytest）
python push.py --dry-run                          # 只渲染不推送，PNG 输出到 out/
DAILY_COUNT=3 GENERATED_COUNT=3 python push.py --dry-run   # 只看生成的题
```

## 需要的 GitHub Secrets

| Secret | 说明 |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | BotFather 发的机器人 token |
| `TELEGRAM_CHAT_ID` | 接收推送的聊天 ID |

> Secrets **不会**跟着 `git push` 走，也不一定跟着仓库转移走。换仓库后记得重设，
> 否则 workflow 会跑起来然后 `KeyError` 挂掉。

---

# 🗺️ Roadmap

原则：**每周最多加一个生成器**，其余时间去做题。写 bot 很容易变成一种
非常有成就感的、逃避学模电的方式。

## 阶段 0 — 地基 ✅

- [x] `core/`：Task/Blank 模型、`build(gid, seed)` 确定性重建、Grader 协议
- [x] `core/quantity.py`：SI 词头 / dB / 单位解析
- [x] `digital/`：记号归一、真值表等价判定、精确 Quine-McCluskey
- [x] 第一个生成器 `sop-simplify`（逻辑代数化简）
- [x] 接驳 `push.py` / `listen.py` / `render.py`，两条通道并行

## 阶段 1 — 把数电题型铺开

- [ ] `number-system`：数制转换、BCD / 格雷码 / 补码
- [ ] `karnaugh`：卡诺图填空、圈图、无关项利用
- [ ] `logic-schematic`：用 schemdraw 画逻辑门图，读图写表达式
- [ ] `sequential`：触发器状态表、计数器模数、自启动判定（模拟状态机出答案）
- [ ] `timing`：时序图（schemdraw 的 timing 模块），波形→状态序列

## 阶段 2 — 记住你错在哪

- [ ] 错题本：判题结果落成 JSON，由 Actions commit 回仓库
- [ ] 间隔重复：Leitner 三档就够，`draw_daily` 按掌握度加权
- [ ] 考前报告：按知识点统计正确率，指出薄弱点

> 现在 `draw_daily` 是纯加权随机，完全不记得你错过什么。
> 对一门 5 学分硬课，这一条的收益大于任何判题逻辑上的精巧。

## 阶段 3 — 开模电

- [ ] `analog/topology.py`：电路拓扑作为唯一真相源
- [ ] `sim/ngspice.py`：走 `subprocess` 调 `ngspice -b` 解析输出
      （**不用 PySpice**，它绑 libngspice 共享库，CI 里折腾成本高）
- [ ] `analog/schematic.py`：schemdraw 出电路图，标注与仿真参数同源
- [ ] `ce-amp`：共射放大电路，Q 点 / $A_v$ / $R_i$ / $R_o$，多空 + 误差传递
- [ ] `analog/faults.py`：故障变异 → 改错题（问故障在哪，或问故障后的 Q 点）
- [ ] **spec 验证判题**：给指标让你设计，把你的参数灌进 SPICE 验达标 —— 
      任何合法解都算对，这是唯一能自动判"设计题"的路子
- [ ] 波形识别：扰动电路生成干扰项，把"画波形"转成四选一

## 阶段 4 — 交互升级

- [ ] 多轮推送：答完第 1 步再推第 2 步（现在是一卡多空、一次答完）
- [ ] `/hint` 命令：按空给提示，不直接给答案
- [ ] `/again <ID>`：换个种子重出同类型的一道

## 不做的事

- **判过程分**。这个 bot 的形状是"验证结果"，不是"批改推导"。
  多步推导按步给分、实验报告、Multisim 仿真作业 —— 这些不在射程内，
  硬改就是重写另一个项目。阶段 3 的 spec 验证是绕过这个限制的办法：
  不判过程，直接验产物。
