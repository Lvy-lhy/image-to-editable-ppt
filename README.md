# 图片转可编辑 PPT

`image-to-editable-ppt` 是一个 Codex 技能：识别参考图片中的文字、结构和素材，再重建为可编辑的 PowerPoint（PPTX）。

## 功能

- 单页图片、幻灯片截图、技术路线图和流程图重建。
- 长截图拆页、跨图去重及互补片段合并。
- 保留参考版式，或套用用户提供的 PPTX 模板。
- 文字、框线、流程模块和箭头使用 PPT 原生对象。
- 照片和真实算法结果作为独立、可替换的图片嵌入。
- 导出后检查页面覆盖、视觉效果及对象可编辑性。

## 实际案例

使用 *Nature Communications*（2024）论文 **Learning representations for image-based profiling of perturbations** 的 Figure 1，展示完整论文图转为可编辑 PPT 的效果。保留 A–G 全部面板。

[下载可编辑 PPT](examples/nature-cell-painting/output.pptx) · [原始图片](examples/nature-cell-painting/input.png) · [案例说明与对象检查](examples/nature-cell-painting/README.md)

**论文原图：**

![Nature Communications Figure 1 原图](examples/nature-cell-painting/input.png)

**可编辑 PPT 的实际渲染：**

![Nature Communications Figure 1 可编辑重建结果](examples/nature-cell-painting/preview.png)

**编辑状态截图（用户提供）：**

![选中多个独立对象时的编辑界面](examples/nature-cell-painting/editing-screenshot.png)

截图中的选择框、控制点和旋转手柄展示了独立对象的选中状态。实际可编辑范围见下方说明。

共 149 个独立对象：41 个原生文本框、98 个图形与连线、10 个独立图片对象。照片、连续密度场及特征向量保留原图像素；其内部标注仍为像素。文字、示意结构及符号经原生重绘，字体与几何外观存在细节差别。没有重新运行论文算法，也没有生成新的实验结果。

图片来源：[Moshkov et al., Nature Communications 15, 1594 (2024), Fig. 1](https://doi.org/10.1038/s41467-024-45999-1)，按 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 使用；PPT 为改编版本，来源与改编说明同时保留在页脚和备注。对象数不能换算为“可编辑百分比”。

## 使用条件

需要支持本地技能的 Codex 环境，以及可用的 `presentations:Presentations` 演示文稿技能与其 JavaScript `@oai/artifact-tool` 运行环境。本仓库只包含图片重建技能和辅助检查脚本，相关应用、模型和运行库需由使用环境提供。

辅助检查脚本使用 Python 3 标准库，无需第三方 Python 依赖。Windows 的 PowerPoint/WPS 自动化是可选的模板适配和渲染方式。

## 安装

将本仓库克隆到 Codex 的 skills 目录。

Windows PowerShell：

```powershell
git clone https://github.com/Lvy-lhy/image-to-editable-ppt.git "$env:USERPROFILE\.codex\skills\image-to-editable-ppt"
```

macOS / Linux：

```bash
git clone https://github.com/Lvy-lhy/image-to-editable-ppt.git "${CODEX_HOME:-$HOME/.codex}/skills/image-to-editable-ppt"
```

如果配置了自定义 `CODEX_HOME`，Windows 也应安装到该目录下的 `skills/image-to-editable-ppt`。已有同名技能时先备份旧版。

也可以从 GitHub 的 **Code → Download ZIP** 下载，解压后将包含 `SKILL.md` 的文件夹命名为 `image-to-editable-ppt`，放入 skills 目录。最终层级应为：

```text
skills/
└── image-to-editable-ppt/
    ├── SKILL.md
    ├── agents/
    ├── references/
    └── scripts/
```

安装后新开 Codex 对话；若尚未识别，重新启动 Codex。

## 使用示例

先上传参考图片，再输入：

```text
$image-to-editable-ppt 将这张图片重建为一页可编辑PPT，保持原图布局，文字、框线和箭头可单独修改。
```

图片与模板一起上传：

```text
$image-to-editable-ppt 将这些图片重建为可编辑PPT，并套用附件中的PPT模板。真实照片和算法结果使用附件原图。
```

长截图：

```text
$image-to-editable-ppt 把这些长截图中可见的页面全部重建为可编辑PPT，去除重复页，标明无法恢复的截断部分。
```

## 可编辑范围

| 内容 | 输出形式 |
| --- | --- |
| 标题、正文、外部标签 | 原生文本框 |
| 边框、色块、流程模块、箭头 | 原生形状与连接线 |
| 表格、具有可核实精确数值的图表 | 原生表格或图表 |
| 照片、热图、真实算法输出、缺少原始数据的科学图 | 独立图片对象 |

图片内部已有的文字和标线仍为像素。低清、遮挡或截断内容不能保证恢复；缺少数据时不按曲线外观猜数值。重建结果需要经过实际渲染检查。

## 检查工具

在仓库目录执行：

```bash
python scripts/inspect_editability.py example.pptx --output editability.json
```

报告统计原生对象，并提示可能覆盖整页的图片。它提供人工复核线索，不能单独证明完整可编辑、视觉一致或连接线已绑定。

运行脚本测试：

```bash
python -m unittest discover -s scripts -p "test_*.py" -v
```

## 文件说明

- [SKILL.md](SKILL.md)：技能入口与工作流程。
- [agents/openai.yaml](agents/openai.yaml)：显示信息和默认提示。
- [references/multi-page.md](references/multi-page.md)：长截图、多页覆盖与样式提取。
- [references/reconstruction.md](references/reconstruction.md)：对象重建、图表及模板适配。
- [scripts/inspect_editability.py](scripts/inspect_editability.py)：只读 PPTX 对象检查。
- [scripts/test_inspect_editability.py](scripts/test_inspect_editability.py)：检查脚本测试。
- [examples/README.md](examples/README.md)：真实转换案例、输入素材、可编辑 PPT 和对象检查结果。

## 验证范围

检查脚本有 8 项自动测试；此前单页重建样例已在本机 WPS 中完成文字、图形、箭头及图片的修改、保存、重开与渲染验证。未验证所有操作系统、Office 版本或接收方环境。
