# HighScoreCaptainCapri 📚

每日自动推送高数 / 大物练习题到 Telegram，支持 LaTeX 渲染与自动判题。
全部跑在 GitHub Actions 上，不需要服务器。

## 工作方式

- **每日推题**（`daily.yml`，北京时间 8:00）：按权重抽取 10 道题（高数、大物都会覆盖），
  每道题渲染成一张 LaTeX 图片卡片（含题图）推送到 Telegram。
- **自动判题**（`listener.yml`，每 2 小时拉起一次，处理积压的答案）：
  - 直接**回复**某道题的消息，内容写答案，机器人回复 ✅/❌；
  - 或发送 `/answer <题目ID> <答案>`；
  - 答案支持 `-14/15`、`-2*pi`、`2e5`、`166 J` 等写法，数值按相对误差（默认 1%）判定。

> 判题最多延迟 ~2 小时（Telegram 会保留未处理消息 24 小时，不会丢）。
> 提交后想立刻出结果，去 Actions 页手动 Run 一次 "Telegram Answer Bot" 即可。
> 若仓库转为公开（Actions 分钟数不限），可按 `listener.yml` 里的注释
> 改成每小时长轮询 55 分钟，获得近乎即时的判题。

## 添加题目

在 `problems/` 下新建一个 markdown 文件（文件名即题目 ID）：

```markdown
---
subject: 高数          # 或 大物
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

## 本地调试

```bash
pip install -r requirements.txt
python -m playwright install chromium
python push.py --dry-run   # 只渲染不推送，PNG 输出到 out/
```

## 需要的 GitHub Secrets

| Secret | 说明 |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | BotFather 发的机器人 token |
| `TELEGRAM_CHAT_ID` | 接收推送的聊天 ID |
