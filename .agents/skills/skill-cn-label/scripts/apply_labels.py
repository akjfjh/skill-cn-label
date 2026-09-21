"""Apply Chinese UI labels to installed Codex skills without changing invocation names."""

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def standard_roots() -> list[Path]:
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex")).expanduser()
    roots = [
        codex_home / "skills",
        home / ".codex" / "skills",
        home / ".agents" / "skills",
    ]
    for parent in (Path.cwd(), *Path.cwd().parents):
        roots.append(parent / ".agents" / "skills")
        if (parent / ".git").exists():
            break
    return roots


def installed_plugins() -> list[dict]:
    """Ask Codex for installed plugins; its active source may differ from its cache."""
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
    bundled_cli = codex_home / "plugins" / ".plugin-appserver" / ("codex.exe" if os.name == "nt" else "codex")
    executable = shutil.which("codex") or (str(bundled_cli) if bundled_cli.is_file() else None)
    if not executable:
        return []
    try:
        result = subprocess.run(
            [executable, "plugin", "list", "--json"],
            capture_output=True, text=True, encoding="utf-8", timeout=15, check=True,
        )
        return json.loads(result.stdout).get("installed", [])
    except (OSError, subprocess.SubprocessError, ValueError):
        return []


def plugin_source_roots(plugins: list[dict]) -> list[Path]:
    return [Path(plugin["source"]["path"]) for plugin in plugins
            if plugin.get("installed") and plugin.get("enabled")
            and plugin.get("source", {}).get("source") == "local"
            and plugin["source"].get("path")]


def find_skills(extra_roots: list[Path] | None = None, plugins: list[dict] | None = None) -> list[Path]:
    found: dict[Path, Path] = {}
    if plugins is None:
        plugins = installed_plugins()
    for root in [*standard_roots(), *plugin_source_roots(plugins), *(extra_roots or [])]:
        if not root.exists():
            continue
        if (root / "SKILL.md").is_file():
            candidates = [root]
        elif root.name == "skills":
            candidates = [child for child in root.iterdir() if (child / "SKILL.md").is_file()]
            system = root / ".system"
            if system.is_dir():
                candidates.extend(child for child in system.iterdir() if (child / "SKILL.md").is_file())
        else:
            candidates = [p.parent for p in root.rglob("SKILL.md") if p.parent.parent.name == "skills"]
        for skill in candidates:
            if skill.name == "skill-cn-label":
                continue
            found.setdefault(skill.resolve(), skill)
    return sorted(found.values(), key=lambda path: (path.name.lower(), str(path).lower()))


def yaml_scalar(value: str) -> str:
    value = value.strip()
    if value.startswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value.strip("'\"")


def frontmatter(skill_md: Path) -> tuple[str, str, str]:
    content = skill_md.read_text(encoding="utf-8-sig")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", content, re.DOTALL)
    if not match:
        return skill_md.parent.name, "", content[:320]
    lines = match.group(1).splitlines()
    fields = {}
    for index, line in enumerate(lines):
        field = re.match(r"^(name|description):\s*(.*)$", line)
        if not field:
            continue
        value = field.group(2)
        if value in {">", ">-", "|", "|-"}:
            following = []
            for next_line in lines[index + 1 :]:
                if next_line and not next_line[0].isspace():
                    break
                following.append(next_line.strip())
            value = " ".join(part for part in following if part)
        fields[field.group(1)] = yaml_scalar(value)
    return fields.get("name", skill_md.parent.name), fields.get("description", ""), content[match.end() :].strip()[:320]


def metadata_field(text: str, key: str) -> str:
    match = re.search(rf"(?m)^\s+{key}:\s*(.*)$", text)
    return yaml_scalar(match.group(1)) if match else ""


def inventory(extra_roots: list[Path] | None = None, include_localized: bool = False,
              plugins: list[dict] | None = None) -> list[dict]:
    items = []
    for skill in find_skills(extra_roots, plugins):
        name, description, body_excerpt = frontmatter(skill / "SKILL.md")
        meta = skill / "agents" / "openai.yaml"
        existing = meta.read_text(encoding="utf-8-sig") if meta.is_file() else ""
        display = metadata_field(existing, "display_name")
        summary = metadata_field(existing, "short_description")
        localized = bool(re.search(r"[\u3400-\u9fff]", display) and re.search(r"[\u3400-\u9fff]", summary))
        if localized and not include_localized:
            continue
        items.append({
            "path": str(skill.resolve()),
            "name": name,
            "description": description,
            "display_name": display,
            "short_description": summary,
            "body_excerpt": body_excerpt,
            "localized": localized,
        })
    return items


def update_metadata(skill_dir: Path, label: str, summary: str, dry_run: bool = False) -> tuple[str, bool]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise ValueError(f"Missing SKILL.md: {skill_dir}")
    if not label.strip() or not summary.strip():
        raise ValueError(f"Missing Chinese label or description: {skill_dir}")

    meta = skill_dir / "agents" / "openai.yaml"
    original = meta.read_bytes().decode("utf-8-sig") if meta.exists() else ""
    newline = "\r\n" if "\r\n" in original else "\n"
    lines = original.splitlines(keepends=True)
    interface = next((i for i, line in enumerate(lines) if re.match(r"^interface:\s*$", line)), None)
    if interface is None:
        lines[0:0] = ["interface:" + newline]
        interface = 0

    end = next(
        (i for i in range(interface + 1, len(lines)) if re.match(r"^[A-Za-z_][\w-]*:\s*", lines[i])),
        len(lines),
    )
    block = lines[interface + 1 : end]
    current = next(
        (re.match(r"^\s+display_name:\s*(.*?)\s*$", line).group(1) for line in block
         if re.match(r"^\s+display_name:", line)),
        None,
    )
    if current:
        title = yaml_scalar(current)
        title = re.sub(r"（[^（）]*[\u3400-\u9fff][^（）]*）$", "", title).rstrip()
    else:
        name, _, _ = frontmatter(skill_md)
        title = name.replace("-", " ").title()

    fields = {
        "display_name": f"{title}（{label}）",
        "short_description": summary,
    }
    for key, value in fields.items():
        replacement = f"  {key}: {json.dumps(value, ensure_ascii=False)}{newline}"
        index = next((i for i, line in enumerate(block) if re.match(rf"^\s+{key}:", line)), None)
        if index is None:
            block.append(replacement)
        else:
            block[index] = replacement
    lines[interface + 1 : end] = block
    updated = "".join(lines)
    changed = updated != original
    if changed and not dry_run:
        meta.parent.mkdir(exist_ok=True)
        meta.write_bytes(updated.encode("utf-8"))
    return fields["display_name"], changed


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    discover = commands.add_parser("discover", help="Write an inventory of skills needing translation")
    discover.add_argument("--output", type=Path, required=True)
    discover.add_argument("--all", action="store_true", help="Include already localized skills")
    discover.add_argument("--root", action="append", type=Path, default=[], help="Additional skill or parent directory")
    apply = commands.add_parser("apply", help="Apply Chinese labels from a JSON manifest")
    apply.add_argument("manifest", type=Path)
    apply.add_argument("--root", action="append", type=Path, default=[], help="Additional skill or parent directory")
    apply.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.command == "discover":
        plugins = installed_plugins()
        items = inventory(args.root, args.all, plugins)
        args.output.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Found {len(items)} skills for the inventory: {args.output}")
        remote = [plugin["pluginId"] for plugin in plugins if plugin.get("source", {}).get("source") == "remote"]
        if remote:
            print("Remote plugin metadata is served by its marketplace and cannot be changed by editing local cache: "
                  + ", ".join(remote))
        return

    labels = json.loads(args.manifest.read_text(encoding="utf-8"))
    plugins = installed_plugins()
    available = find_skills(args.root, plugins)
    by_path = {str(skill.resolve()): skill for skill in available}
    selected = []
    if isinstance(labels, list):
        for item in labels:
            path = str(Path(item["path"]).expanduser().resolve())
            if path not in by_path:
                raise ValueError(f"Skill not found in discovered roots: {path}")
            selected.append((by_path[path], item))
    elif isinstance(labels, dict):
        selected = [(skill, labels[skill.name]) for skill in available if skill.name in labels]
    else:
        raise ValueError("Manifest must be a list of path entries or a map by skill folder name")

    changed = 0
    for skill, item in selected:
        title, did_change = update_metadata(skill, item["label"], item["short_description"], args.dry_run)
        changed += did_change
        action = "would update" if args.dry_run and did_change else "updated" if did_change else "unchanged"
        print(f"{action}: {skill.name} → {title}")
    print(f"Matched {len(selected)} skills; {'would change' if args.dry_run else 'changed'} {changed}")


if __name__ == "__main__":
    main()
