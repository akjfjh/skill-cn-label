import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from apply_labels import find_skills, inventory, update_metadata


class UpdateMetadataTest(unittest.TestCase):
    def test_preserves_other_fields_and_replaces_existing_chinese_label(self):
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "code-review"
            (skill / "agents").mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: code-review\ndescription: Review code.\n---\n", encoding="utf-8")
            meta = skill / "agents" / "openai.yaml"
            meta.write_text(
                'interface:\n  display_name: "Code Review（旧说明）"\n'
                '  short_description: "Old"\n  icon_large: "./assets/icon.png"\n'
                'policy:\n  allow_implicit_invocation: false\n',
                encoding="utf-8",
            )
            title, changed = update_metadata(skill, "审查代码变更", "按规范审查代码")
            self.assertEqual(title, "Code Review（审查代码变更）")
            self.assertTrue(changed)
            self.assertIn('icon_large: "./assets/icon.png"', meta.read_text(encoding="utf-8"))
            self.assertIn("allow_implicit_invocation: false", meta.read_text(encoding="utf-8"))
            self.assertEqual(update_metadata(skill, "审查代码变更", "按规范审查代码")[1], False)

    def test_creates_metadata_when_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            skill = Path(directory) / "find-skills"
            skill.mkdir()
            (skill / "SKILL.md").write_text("---\nname: search-skills\ndescription: Find skills.\n---\n", encoding="utf-8")
            title, changed = update_metadata(skill, "查找技能", "查找适合任务的技能")
            self.assertTrue(changed)
            self.assertEqual(title, "Search Skills（查找技能）")
            self.assertIn("short_description:", (skill / "agents" / "openai.yaml").read_text(encoding="utf-8"))

    def test_discovers_new_skill_without_a_preset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skills"
            skill = root / "github-helper"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: github-helper\ndescription: >\n"
                "  Summarize GitHub issues\n  and prepare a work plan.\n---\n"
                "# GitHub Helper\nRead issues and propose next steps.\n",
                encoding="utf-8",
            )
            self.assertIn(skill, find_skills([root]))
            item = next(entry for entry in inventory([root]) if entry["name"] == "github-helper")
            self.assertEqual(item["description"], "Summarize GitHub issues and prepare a work plan.")
            self.assertFalse(item["localized"])
            update_metadata(skill, "整理GitHub议题", "汇总议题并制定工作计划")
            self.assertFalse(any(entry["name"] == "github-helper" for entry in inventory([root])))

    def test_cli_applies_path_manifest_after_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skills"
            skill = root / "new-skill"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: new-skill\ndescription: Make a report.\n---\n",
                encoding="utf-8",
            )
            manifest = Path(directory) / "translations.json"
            manifest.write_text(json.dumps([{
                "path": str(skill.resolve()),
                "label": "生成报告",
                "short_description": "整理资料并生成报告",
            }], ensure_ascii=False), encoding="utf-8")
            script = Path(__file__).resolve().parents[1] / "scripts" / "apply_labels.py"
            command = [sys.executable, "-B", str(script), "apply", str(manifest), "--root", str(root)]
            subprocess.run([*command, "--dry-run"], check=True, capture_output=True)
            self.assertFalse((skill / "agents" / "openai.yaml").exists())
            subprocess.run(command, check=True, capture_output=True)
            self.assertIn("New Skill（生成报告）", (skill / "agents" / "openai.yaml").read_text(encoding="utf-8"))

    def test_uses_active_local_plugin_source_not_translated_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            cache = base / "plugins" / "cache" / "example" / "skills" / "documents"
            source = base / "runtime" / "plugins" / "documents" / "skills" / "documents"
            for skill in (cache, source):
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text("---\nname: documents\ndescription: Edit documents.\n---\n", encoding="utf-8")
            (cache / "agents").mkdir()
            (cache / "agents" / "openai.yaml").write_text(
                'interface:\n  display_name: "Documents（编辑文档）"\n  short_description: "编辑文档"\n',
                encoding="utf-8",
            )
            plugins = [
                {"installed": True, "enabled": True, "source": {"source": "local", "path": str(source.parents[1])}},
                {"installed": True, "enabled": True, "source": {"source": "remote", "id": "online"}},
            ]
            with patch("apply_labels.standard_roots", return_value=[]):
                self.assertEqual(find_skills(plugins=plugins), [source])
                entries = inventory(plugins=plugins)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["path"], str(source.resolve()))
            self.assertFalse(entries[0]["localized"])

    def test_discovers_builtin_system_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skills"
            skill = root / ".system" / "skill-creator"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: skill-creator\ndescription: Create a skill.\n---\n", encoding="utf-8",
            )
            with patch("apply_labels.standard_roots", return_value=[]):
                self.assertEqual(find_skills([root], plugins=[]), [skill])


if __name__ == "__main__":
    unittest.main()
