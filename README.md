# Skill 中文用途标注

这个 Codex skill **自动发现本地技能**，由 Codex 读取技能说明并生成中文用途括注，同时将技能列表中的简介翻译成中文。例如：

```yaml
interface:
  display_name: "Code Review（审查代码变更）"
  short_description: "按项目规范和需求审查代码差异"
```

原技能的 `SKILL.md` 中的 `name` 不变，仍用原来的 `$code-review` 调用。

## 使用

本项目的技能位于 [`.agents/skills/skill-cn-label`](.agents/skills/skill-cn-label)。让 Codex 执行：

```text
使用 $skill-installer 安装 https://github.com/akjfjh/skill-cn-label/tree/main/.agents/skills/skill-cn-label
```

也可以将该目录复制到个人技能目录。安装后直接说：

```text
使用 $skill-cn-label 自动汉化我本地的 skills。
```

无需列出技能或手写翻译。技能会扫描 Codex 用户目录（含 `.system` 内置技能）、当前项目的 `.agents/skills`，并通过 `codex plugin list --json` 找到已安装本地插件的实际来源；如有其他存放位置，可以在请求中附上目录。扫描脚本使用 Python 3.10+ 标准库，不调用外部翻译 API；Codex 根据每个技能的说明生成中文文字。没有 Python 时，技能会改用可用的文件搜索工具。

附带的 [已知技能翻译清单](.agents/skills/skill-cn-label/labels.zh-CN.json) 是可选示例；新用户不依赖这份清单。批量脚本只更新每个技能的 `agents/openai.yaml` 中的 `display_name` 和 `short_description`，其余元数据与技能正文保持原样。在线插件的菜单文字由远端插件目录提供，修改本地缓存不能让它们汉化，脚本会报告这类插件。插件更新可能覆盖本地来源内的中文标注；保留运行时生成的翻译清单即可重新应用。

这是一项**按需调用**的 Codex skill：安装新技能后再调用一次即可识别并汉化新内容。它不会在后台监控安装事件。

## 验证

```text
python -m unittest discover -s .agents/skills/skill-cn-label/tests
```

## 许可

本项目使用 MIT License，详见仓库根目录的 `LICENSE`。
