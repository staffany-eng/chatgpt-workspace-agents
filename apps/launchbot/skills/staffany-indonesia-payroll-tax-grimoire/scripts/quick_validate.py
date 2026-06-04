#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate staffany-indonesia-payroll-tax-grimoire package."
    )
    parser.add_argument(
        "bundle_path",
        help="Path to extracted bundle root (contains manifest.json)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle_path = pathlib.Path(args.bundle_path).resolve()

    errors: List[str] = []
    manifest_path = bundle_path / "manifest.json"
    manifest = None
    if not manifest_path.exists():
        errors.append("Missing manifest.json")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append("manifest.json is not valid JSON")

    if manifest:
        skills = manifest.get("skills", [])
        if not isinstance(skills, list) or not skills:
            errors.append("manifest.json has empty or invalid 'skills'")
        else:
            for skill in skills:
                skill_name = skill.get("name")
                skill_rel_path = skill.get("path")
                is_required = bool(skill.get("required"))
                if not skill_name or not skill_rel_path:
                    errors.append(f"Invalid skill entry: {skill}")
                    continue
                skill_path = bundle_path / skill_rel_path
                has_skill = (skill_path / "SKILL.md").exists()
                if is_required and not has_skill:
                    errors.append(
                        f"Missing required SKILL.md for {skill_name} at {skill_rel_path}"
                    )

    required_paths = [
        "SKILL.md",
        "README.md",
        "VERSION",
        "scripts/quick_validate.py",
    ]
    for rel in required_paths:
        if not (bundle_path / rel).exists():
            errors.append(f"Missing required path: {rel}")

    kb_validator = (
        bundle_path
        / "skills"
        / "indonesia-tax-knowledge-updater"
        / "scripts"
        / "validate_knowledge_bank.rb"
    )
    if kb_validator.exists():
        result = subprocess.run(
            ["ruby", str(kb_validator)],
            cwd=bundle_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if result.returncode != 0:
            errors.append("Knowledge-bank validator failed:\n" + result.stdout)

    if errors:
        print("Validation failed:")
        for err in errors:
            print(f"- {err}")
        return 2

    print("Validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
