# 贡献指南 · Contributing Guide

感谢你愿意为 ZCode 提交反馈！这份指南会帮你写出"维护者一看就懂、能马上推进"的高质量 issue。
Thanks for contributing to ZCode! This guide helps you file high-signal issues that maintainers can act on quickly.

---

## 1. 提交前请先做的事 · Before You Submit

- ✅ 在 [Issues](../../issues?q=is%3Aissue) 和 [Discussions](../../discussions) **搜一下**，看看是否已有相同反馈。如果有，给它点 👍 或在评论里补充信息，比新开一条更有用。
  *Search existing issues and discussions first. Upvoting or commenting on an existing one is more useful than opening a duplicate.*
- ✅ 拿不准是建议、Bug 还是使用问题？看下表分流。
  *Unsure where to post? See the table below.*

| 你的情况 / Your case | 去哪里 / Where |
| --- | --- |
| 我想要个新功能 / 我希望某个地方更顺手 | **Issue** → 功能建议模板 |
| 产品出现异常、报错、行为不符合预期 | **Issue** → Bug 模板 |
| 我不知道某个功能怎么用 / 想问最佳实践 | **Discussions → Q&A** |
| 有个模糊的想法想和大家聊聊 | **Discussions → Ideas** |
| 发现了安全漏洞 | 见 [SECURITY.md](./SECURITY.md)（**不要公开提**） |

---

## 2. 一条好 Issue 长什么样 · Anatomy of a Good Issue

### 功能建议 / Feature Request

| 字段 / Field | 写什么 / What to write |
| --- | --- |
| **使用场景 / Context** | 你在做什么、卡在哪 |
| **建议方案 / Proposal** | 你希望产品怎么改 |
| **预期价值 / Value** | 这个改动能带来什么好处 |

> ❌ 反例 / Bad: "希望加个 X 功能" / "Please add X"
> ✅ 正例 / Good: "我每周三导出报表时都要手动切换 5 次 Y，建议在导出弹窗记住上次选择，能节省 ~30 秒。"

### Bug 报告 / Bug Report

务必包含 / Must include:
- **复现步骤**（一步一步） / *Reproduction steps (numbered)*
- **期望表现 vs 实际表现** / *Expected vs actual*
- **版本 & 环境**（设备、系统、浏览器） / *Version & environment*
- **截图 / 录屏 / 日志**（强烈推荐） / *Screenshots, recordings, logs (highly recommended)*

---

## 3. Issue 的一生 · Issue Lifecycle

```
你提交 → status: 待评估
       ↓
   维护者评估（会尽快给出首次响应）
       ↓
   ┌── 信息不足 → needs: 更多信息（等你补充）
   ├── 不采纳 → status: 已拒绝（评论说明原因，关闭）
   └── 采纳 → status: 已采纳 → 开发中 → 已上线（关闭）
```

- 我们会用评论同步进展。
  *We'll keep you posted via comments.*
- 长时间无活动的 issue 会被标记 `stale`，30 天后自动关闭（可重新打开）。
  *Inactive issues get a `stale` label and auto-close after 30 days. They can be reopened.*

---

## 4. 行为规范 · Code of Conduct

参与本仓库的所有讨论需遵守 [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)。
All interactions must follow our [Code of Conduct](./CODE_OF_CONDUCT.md).

---

## 5. 常见问答 · FAQ

**Q：我可以一次提多个建议吗？/ Can I submit multiple suggestions in one issue?**
A：请一个 issue 一个主题，方便单独评估和跟踪。
*Please file one topic per issue so we can track each independently.*

**Q：我的建议被拒了，能再讨论吗？/ My suggestion was declined — can we discuss?**
A：可以，在原 issue 评论里继续讨论；若有新的论据，可申请重开。
*Yes — comment on the original issue. With new arguments, we can reconsider.*

**Q：我能看到内部排期吗？/ Can I see the internal schedule?**
A：[ROADMAP.md](./ROADMAP.md) 公示季度方向；具体 sprint 排期不对外。
*[ROADMAP.md](./ROADMAP.md) shows quarterly direction. Per-sprint scheduling is internal.*
