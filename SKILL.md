---
name: section-evidence-notes
description: Produce reusable research notes aligned to a paper's actual sections, with field-level evidence, study conditions and limitations. Use when reading one or more scientific papers to build section summaries, comparison cards or searchable knowledge notes.
---

# 章节与证据笔记

## 先确定本案要交什么

读取 `/input/case.json`、`/input/task.md` 和实际材料。记下指定读者、问题、语言、页段、文件、输出字段和嵌套类型。区分正文、预印本、勘误和补充材料的版本。若材料是综述，记录作者如何组织证据及不同研究的分歧；若是理论论文，记录假设、命题和适用域；实证论文则保留样本、比较对象、实验设置、评价指标、结果和边界。以论文自己的章节推进论证，再从笔记生成可比较的卡片。

## 读原文并建立索引

```sh
cd /skills/weekly-skill
python scripts/notes.py index --input /input --work /app/work/notes
```

默认处理输入目录中的 PDF、TXT、Markdown。使用一个或多个 `--source materials/paper.pdf` 可精确指定材料，避免把附带说明当成论文。开发和运行脚本仅使用 Python 3.9+ 标准库；PDF 另需 Poppler 的 `pdftotext` 或 PyMuPDF。输入可随页数增长；按 `index.json` 的 `documents → dN → pages` 逐页取用。每页同时保存 `body` 行和 `layout` 行；换页符划分物理页，行号从 1 开始，二者行号不可互换。稀疏扫描页可加 `--ocr-lang eng`（中文用已安装的相应语言包），需要现有 `pdftoppm` 和 `tesseract`。核对不清的 OCR 数字、符号和图例时，用 `pdftoppm -f N -l N -r 180 -png FILE PREFIX` 查看原页。缺少语言包、密码、图片或附件时，注明具体页和阻塞字段。

先顺着目录、正文标题和过渡句恢复章节树。双栏页分别核对栏首、栏尾、跨栏图表，表格优先看 layout 和源页。每个实质章节写出“本节回答什么、用了什么依据、如何导向下一节”，把答案落实为可单独检索的一条或数条笔记。避免让同一个摘要段代替整篇。长文先完成最关键的问题、结果与限制并保存第一份可用草稿。

## 编写可执行草稿

在 `/app/work/notes/draft.json` 写入以下数据，完整可运行样式见 [合成草稿](examples/draft.json)。

| 字段 | 写入什么 |
|---|---|
| `case_id, title, sections` | 原输入标识、论文题名、按原序排列的标题。脚本回查每个标题；翻译标题、跨行标题或多个文件同名小节，用 `section_refs` 将显示名称映射到唯一的原文锚点。无显式标题时说明依据，勿虚构章节名。 |
| `notes[]` | 每条含唯一 `id`、`section`、`kind`、`claim`、`state`、`evidence` 和检索用 `tags`。一句主要断言；有条件的结论须把条件写入正文。作者报告、作者解释和读者推论用 kind 或 basis 标出。 |
| `evidence[]` | `doc, page, quote` 必填；可选 `view, location, role, line`。写最短且足以定位的原文片段以及题号、图号、公式或小节。选择 body 或 layout。重复短语用更长上下文或明确起始行消歧；不要凭文献题名配引文。 |
| `measurement` | 对可机器核对的独立表格数值附上 `row_label,column,value,unit,condition`，数字保留原显示精度。附四种角色的证据：同页 layout 表头、数据行、含单位的题注、解释条件的注释或方法。表格多层表头、转页、缺失单位或无法对齐时，回看源页，记录实际表/行/列与复核方法；不使用自动单元格断言。图中估读应标“约”及范围；不要把像素估计写成精确测量。 |
| `state, basis` | `supported` 要有直接证据；`not_reported` 写查过的范围；`uncertain` 写歧义；`conflicting` 分别保留冲突来源和条件；`unreadable` 写无法阅读的位置。机器检查定位和匹配，Agent 仍需核实语义、比较方向、单位和推广范围。 |
| `card, aliases` | 卡片每个字段映射到笔记 ID 数组，覆盖问题、数据、方法、关键发现、结论和限制。合并有根据的简称、译名或同义词；同字异义的变量按实体/文档区分。多篇对比另写逐文卡片，分别保留数据、条件、结论及 ID；只有度量和条件可比时才汇总。 |
| `contract_fields, status, uncertainties, changes` | 案例专属字段在 contract_fields 中填真实值、结构或路径；保存原始 output_contract。记录缺口，以及人工更正的原值、现值、原因和锚点。成功、部分、无法判断或失败分别用 success、partial、unable_to_determine、failed。 |

## 生成、审查、复用

```sh
python scripts/notes.py build --input /input --work /app/work/notes --output /app/output
python scripts/notes.py search --output /app/output --query "待检索术语"
```

打开 `notes.md` 看论证顺序，点击证据链接在 `evidence.md` 中找到相应源文件、物理页、视图和行号；用 `result.json` 中的 SHA-256 核对材料版本。回查最重要数值的原行、相邻列、单位、基准及条件。对“未报告”的内容检查方法、补充材料和脚注。不同实验设置间出现差异时，保留各自数值和适用条件。

确认 `paper_card`、`section_notes`、`knowledge_index` 能返回到真实笔记 ID，再逐项检查**原案例**所有字段、嵌套类型、指定文件和路径。必要时按案例格式转换这些中间产物并重新打开终稿；Office 成品生成真实 PDF/PNG 预览。脚本验证常见 schema 子集；复杂契约以原始说明为准。若定位或编译失败，根据诊断修正本次草稿；材料确实不足时仍须在指定目录留下有原始 case_id、原契约、已核实主结果及缺口的部分交付。避免重复使用上次运行的成功结果。
