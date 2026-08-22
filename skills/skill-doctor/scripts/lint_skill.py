#!/usr/bin/env python3
"""Lint a Claude Code skill: frontmatter, description quality, structure, and dead references.

The check that matters most is the description. A skill that never triggers is
equivalent to a skill that does not exist, and triggering is decided almost entirely
by the description field - so most of the rules below are about whether the
description names concrete situations rather than describing a capability in the
abstract.

Usage:
    python3 lint_skill.py path/to/skill/
    python3 lint_skill.py path/to/skills/ --recursive
    python3 lint_skill.py path/to/skill/ --json

Exit codes: 0 = clean, 1 = warnings only, 2 = errors.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"

# Rough guidance rather than hard limits: the metadata sits in context permanently,
# so a bloated description costs every conversation, not just the ones that use the skill.
# 900 rather than something tighter: descriptions carry trigger situations, and the
# situations are what make a skill fire. Past ~900 the extra text is usually restatement,
# which costs context in every conversation without adding matching power.
DESC_MIN, DESC_SOFT_MAX, DESC_HARD_MAX = 60, 900, 1024
BODY_SOFT_MAX_LINES = 500

TRIGGER_MARKERS = ("use this", "use it", "whenever", "when the user", "when someone",
                   "triggers on", "use when")
VAGUE_OPENERS = ("helps", "helper for", "utility for", "tool for", "a skill for",
                 "this skill", "used to")


class Finding:
    def __init__(self, level: str, rule: str, message: str, fix: str = ""):
        self.level, self.rule, self.message, self.fix = level, rule, message, fix

    def as_dict(self):
        return {"level": self.level, "rule": self.rule, "message": self.message, "fix": self.fix}


def parse_frontmatter(text: str):
    """Return (frontmatter dict, body, error). Deliberately minimal - no YAML dependency."""
    if not text.startswith("---"):
        return {}, text, "SKILL.md does not start with YAML frontmatter (--- on line 1)."
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text, "Frontmatter is never closed - no second --- line."

    raw, body = text[3:end], text[end + 4:]
    data, key = {}, None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if match:
            key = match.group(1)
            data[key] = match.group(2).strip().strip("'\"")
        elif key and line.startswith((" ", "\t", ">")):
            data[key] = (data[key] + " " + line.strip()).strip()
    return data, body, None


def check_description(desc: str, name: str) -> list:
    findings = []
    if not desc:
        return [Finding(ERROR, "description-missing",
                        "No description field. Without it the skill is invisible to the model - "
                        "the description is the only thing Claude sees when deciding to load a skill.")]

    length = len(desc)
    if length < DESC_MIN:
        findings.append(Finding(
            ERROR, "description-too-short",
            f"Description is {length} characters. Too short to describe both what the skill "
            f"does and when to reach for it.",
            "Name the concrete situations: the phrases a user would actually type."))
    elif length > DESC_HARD_MAX:
        findings.append(Finding(
            ERROR, "description-too-long",
            f"Description is {length} characters, over the {DESC_HARD_MAX} limit.", ""))
    elif length > DESC_SOFT_MAX:
        findings.append(Finding(
            WARN, "description-long",
            f"Description is {length} characters. It sits in context permanently, so every "
            f"conversation pays for it whether or not the skill is used.",
            "Cut the restatements; keep the trigger situations."))

    lowered = desc.lower()
    if not any(marker in lowered for marker in TRIGGER_MARKERS):
        findings.append(Finding(
            WARN, "description-no-triggers",
            "Description says what the skill does but never says when to use it.",
            "Add explicit trigger language - 'Use this whenever ...' followed by concrete "
            "situations. Skills under-trigger far more often than they over-trigger."))

    if any(lowered.startswith(opener) for opener in VAGUE_OPENERS):
        findings.append(Finding(
            INFO, "description-vague-opener",
            "Description opens with a generic phrase.",
            "Lead with the specific capability instead - the first clause does most of the "
            "matching work."))

    # Do the words in the skill's name show up in the description at all? Matching on the
    # exact hyphenated string is too strict - "sql-safety-review" legitimately appears as
    # "Review SQL for destructive ... behaviour". Look for the individual words instead.
    tokens = [t for t in re.split(r"[-_\s]+", name.lower()) if len(t) > 2]
    if tokens:
        present = sum(1 for t in tokens if t in lowered)
        if present < max(1, len(tokens) * 0.6):
            missing = [t for t in tokens if t not in lowered]
            findings.append(Finding(
                INFO, "description-omits-name",
                f"The description barely echoes the skill's own subject "
                f"(missing: {', '.join(missing)}).",
                "Not fatal, but the name's own words are free matching signal."))

    if desc.count(".") <= 1 and length > 200:
        findings.append(Finding(
            INFO, "description-one-sentence",
            "A long single sentence is harder to match against than two or three.", ""))
    return findings


def check_body(body: str, skill_dir: Path) -> list:
    findings = []
    lines = body.splitlines()

    if len(lines) > BODY_SOFT_MAX_LINES:
        findings.append(Finding(
            WARN, "body-long",
            f"SKILL.md body is {len(lines)} lines, past the ~{BODY_SOFT_MAX_LINES}-line "
            f"guideline. The whole body loads whenever the skill triggers.",
            "Move detail into references/ and point at it from the body, so it loads only "
            "when it is actually needed."))

    if not re.search(r"^#\s+\S", body, re.M):
        findings.append(Finding(WARN, "body-no-title",
                                "No top-level heading in the body.", ""))

    if len(body.strip()) < 200:
        findings.append(Finding(ERROR, "body-empty",
                                "The body is essentially empty - the frontmatter is not a skill.", ""))

    shouty = re.findall(r"\b(ALWAYS|NEVER|MUST|DO NOT)\b", body)
    if len(shouty) > 6:
        findings.append(Finding(
            INFO, "body-shouty",
            f"{len(shouty)} instances of ALWAYS/NEVER/MUST/DO NOT.",
            "Explaining why a rule exists generalises better than emphasis: a model that "
            "understands the reason handles the case you did not anticipate."))

    # Dead references: paths mentioned in the body that do not exist on disk.
    referenced = set(re.findall(r"(?:scripts|references|assets|examples)/[\w./-]+", body))
    for path in sorted(referenced):
        clean = path.rstrip(".,);:`")
        if not (skill_dir / clean).exists():
            findings.append(Finding(
                ERROR, "dead-reference",
                f"Body points at '{clean}', which does not exist.",
                "A reference the model cannot open is worse than no reference - it will try."))

    # Bundled files nobody mentions: dead weight, or a missing pointer.
    for folder in ("scripts", "references", "assets", "examples"):
        directory = skill_dir / folder
        if not directory.is_dir():
            continue
        for item in sorted(directory.rglob("*")):
            # __pycache__ and other generated artefacts are not authored content, and
            # reporting them trains the reader to ignore this rule.
            if any(part.startswith((".", "__")) for part in item.relative_to(skill_dir).parts):
                continue
            if item.is_file() and not item.name.startswith("."):
                rel = str(item.relative_to(skill_dir))
                if rel not in body and item.name not in body:
                    findings.append(Finding(
                        WARN, "unreferenced-file",
                        f"'{rel}' is bundled but never mentioned in SKILL.md.",
                        "Either point at it and say when to read it, or drop it."))
    return findings


def check_layout(skill_dir: Path, name: str) -> list:
    findings = []
    if name and skill_dir.name != name:
        findings.append(Finding(
            WARN, "name-mismatch",
            f"Directory is '{skill_dir.name}' but frontmatter name is '{name}'.",
            "Keep them identical - tooling matches on one or the other and the mismatch "
            "surfaces as a skill that cannot be found."))
    if name and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        findings.append(Finding(
            ERROR, "name-format",
            f"Name '{name}' is not lowercase-hyphenated.", "Use letters, digits and hyphens."))

    for script in sorted((skill_dir / "scripts").glob("*.py")) if (skill_dir / "scripts").is_dir() else []:
        head = script.read_text(encoding="utf-8", errors="replace")[:400]
        if not head.startswith("#!"):
            findings.append(Finding(INFO, "script-no-shebang",
                                    f"scripts/{script.name} has no shebang line.", ""))
        if '"""' not in head:
            findings.append(Finding(
                WARN, "script-no-docstring",
                f"scripts/{script.name} has no module docstring.",
                "The docstring is how the model learns what the script does and how to call it."))
    return findings


def lint(skill_dir: Path) -> tuple[list, str]:
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return [Finding(ERROR, "no-skill-md", f"No SKILL.md in {skill_dir}", "")], skill_dir.name

    text = skill_file.read_text(encoding="utf-8")
    frontmatter, body, error = parse_frontmatter(text)
    if error:
        return [Finding(ERROR, "frontmatter", error, "")], skill_dir.name

    name = frontmatter.get("name", "")
    findings: list[Finding] = []
    if not name:
        findings.append(Finding(ERROR, "name-missing", "No name field in frontmatter.", ""))
    findings += check_description(frontmatter.get("description", ""), name)
    findings += check_body(body, skill_dir)
    findings += check_layout(skill_dir, name)
    return findings, name or skill_dir.name


def render(name: str, findings: list) -> str:
    counts = {level: sum(1 for f in findings if f.level == level) for level in (ERROR, WARN, INFO)}
    header = f"{name}: {counts[ERROR]} error(s), {counts[WARN]} warning(s), {counts[INFO]} note(s)"
    lines = [header, "-" * len(header)]
    if not findings:
        lines.append("Clean.")
    for level in (ERROR, WARN, INFO):
        for finding in [f for f in findings if f.level == level]:
            lines.append(f"[{level}] {finding.rule}: {finding.message}")
            if finding.fix:
                lines.append(f"        -> {finding.fix}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", help="a skill directory, or a directory of skills with --recursive")
    parser.add_argument("--recursive", "-r", action="store_true",
                        help="lint every immediate subdirectory containing a SKILL.md")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"No such path: {root}", file=sys.stderr)
        return 2

    targets = (sorted(p for p in root.iterdir() if (p / "SKILL.md").is_file())
               if args.recursive else [root])
    if not targets:
        print(f"No skills found under {root}", file=sys.stderr)
        return 2

    results, worst = [], 0
    for target in targets:
        findings, name = lint(target)
        results.append((name, target, findings))
        if any(f.level == ERROR for f in findings):
            worst = 2
        elif any(f.level == WARN for f in findings) and worst < 1:
            worst = 1

    if args.json:
        print(json.dumps([{"skill": name, "path": str(path),
                           "findings": [f.as_dict() for f in findings]}
                          for name, path, findings in results], indent=2))
    else:
        for index, (name, _, findings) in enumerate(results):
            if index:
                print()
            print(render(name, findings))
    return worst


if __name__ == "__main__":
    sys.exit(main())
