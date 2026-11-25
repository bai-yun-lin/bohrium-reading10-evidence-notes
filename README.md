# 阅读10｜可回查的论文笔记

同一个错误率附近经常并排出现多个数据集、模型和实验条件。本 Skill 把一条笔记的原文锚点、数值、行列条件以及论文中的位置一同保留。执行 Agent 负责读懂论文并写作；脚本负责定位引文、检查结构、复核可对齐的表格单元格和生成可检索结果。

## 跑通合成例子

需要 Python 3.9+。合成示例为文本，不需要第三方包。

```sh
python scripts/notes.py index --input examples/input --work demo/work
python scripts/notes.py build --input examples/input --work demo/work --draft examples/draft.json --output demo/output
python scripts/notes.py search --output demo/output --query warm-up
python scripts/selftest.py
```

**示意输出**：一台仪器预热十分钟后的读数为 **10.5 ms**。同一行的冷态值是 **12.8 ms**。检索 `warm-up` 或“预热”都能找到条件笔记和实测结果；方差保留为未报告。可编辑的章节笔记与逐条证据分别位于 `demo/output/notes.md`、`evidence.md`，机器可读卡片、索引和原契约位于 `result.json`。

## 一版生成、一次复核迭代

开发时用 Huang 等的 DenseNet 论文实际生成中文笔记。在相同 PDF 及同一份解析索引上，第一版有 9 条笔记；Table 2 的关键结果仅有数据行锚点，缺少用于排除邻列的证据。验证案例要求的三种顶层输出也未生成。

优化版有 13 条笔记、11 个已回查的原文章节标题，以及论文卡片、章节索引和术语索引。Table 2 的数值附上数据行、表头、含单位的题注及增强条件。复核物理第 5 页，250 层 DenseNet-BC、k=24 的 C10+ 错误率为 3.62%，同一行 C100+ 为 17.60%。在数值不变的情况下故意把列名改为 C100+，编译器拒绝该笔记。两版均使用同一份原始材料；这个开发对照并非赛事基础 Agent 的成绩。[验证用原论文](https://arxiv.org/abs/1608.06993)

自测另覆盖别名检索、重复 ID、无效页码、悬空卡片、缺锚点、缺失字段和重复运行。原论文、正式案例答案及会话日志不作为 Skill 资源。维持方法时，应同时测试一条正确笔记以及行相同、条件不同的错误笔记。运行范围、字段和异常处理参见 [SKILL.md](SKILL.md)。
