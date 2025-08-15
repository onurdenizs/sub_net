#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Print a directory tree structure with optional depth, exclusions, and output file.

Usage:
  python print_structure.py "D:\\PhD\\dec2025" --max-depth 5 --exclude .git __pycache__ --out structure.txt
"""

import argparse
import os
from pathlib import Path
from typing import Iterable, List, Set

DEFAULT_EXCLUDES = {".git", "__pycache__", ".ipynb_checkpoints"}

def should_exclude(name: str, exclude_set: Set[str]) -> bool:
    # Exclude if exact match of a directory/file name (case-insensitive on Windows)
    return name.lower() in {e.lower() for e in exclude_set}

def list_dir(path: Path) -> (List[Path], List[Path]):
    dirs, files = [], []
    try:
        for p in path.iterdir():
            if p.is_dir():
                dirs.append(p)
            else:
                files.append(p)
    except PermissionError:
        return [], []
    return sorted(dirs, key=lambda x: x.name.lower()), sorted(files, key=lambda x: x.name.lower())

def build_tree_lines(root: Path, max_depth: int, exclude: Set[str], include_files: bool) -> List[str]:
    lines: List[str] = []
    total_dirs = 0
    total_files = 0

    def recurse(current: Path, prefix: str, depth: int):
        nonlocal total_dirs, total_files

        dirs, files = list_dir(current)
        # Filter by exclusions
        dirs = [d for d in dirs if not should_exclude(d.name, exclude)]
        if include_files:
            files = [f for f in files if not should_exclude(f.name, exclude)]
        else:
            files = []

        entries = dirs + files
        count = len(entries)
        for idx, entry in enumerate(entries):
            connector = "└── " if idx == count - 1 else "├── "
            line = f"{prefix}{connector}{entry.name}"
            lines.append(line)

            if entry.is_dir():
                total_dirs += 1
                if max_depth is None or depth < max_depth:
                    extension = "    " if idx == count - 1 else "│   "
                    recurse(entry, prefix + extension, depth + 1)
            else:
                total_files += 1

    # Header
    header = f"{root.resolve()}"
    lines.append(header)
    recurse(root, "", 1)
    # Summary
    lines.append("")
    lines.append(f"📦 Summary: {total_dirs} dirs, {total_files} files")
    return lines

def main():
    parser = argparse.ArgumentParser(description="Print a directory tree structure.")
    parser.add_argument("root", type=str, help="Root directory to print.")
    parser.add_argument("--max-depth", type=int, default=None, help="Maximum depth to traverse (default: no limit).")
    parser.add_argument("--exclude", nargs="*", default=[], help="Names of dirs/files to exclude (space-separated).")
    parser.add_argument("--no-files", action="store_true", help="Do not list files, only directories.")
    parser.add_argument("--out", type=str, default=None, help="Optional output .txt file path.")
    args = parser.parse_args()

    root = Path(args.root).expanduser()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Path not found or not a directory: {root}")

    # Merge defaults with user excludes
    exclude: Set[str] = set(DEFAULT_EXCLUDES) | set(args.exclude or [])

    lines = build_tree_lines(
        root=root,
        max_depth=args.max_depth,
        exclude=exclude,
        include_files=not args.no_files,
    )

    text = "\n".join(lines)
    print(text)

    if args.out:
        out_path = Path(args.out)
        # If only a filename is given, place it under the root
        if not out_path.is_absolute():
            out_path = root / out_path
        out_path.write_text(text, encoding="utf-8")
        print(f"\n✅ Saved to: {out_path}")

if __name__ == "__main__":
    main()
