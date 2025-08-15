import os, sys, pathlib

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
MAX_DEPTH = int(sys.argv[2]) if len(sys.argv) > 2 else 4
EXCLUDE = {".git", "__pycache__", ".ipynb_checkpoints", "output", "SUMO", "archive"}

print(ROOT)
base_parts = len(ROOT.parts)

for cur, dirs, files in os.walk(ROOT):
    rel_depth = len(pathlib.Path(cur).parts) - base_parts
    # Derinlik sınırı
    if rel_depth >= MAX_DEPTH:
        dirs[:] = []  # Daha derine inme
        continue
    # Hariç tutmalar
    dirs[:] = [d for d in dirs if d not in EXCLUDE]

    # Yazdır (sadece klasör adları)
    for i, d in enumerate(sorted(dirs, key=str.lower)):
        is_last = (i == len(dirs) - 1)
        prefix = "│   " * rel_depth + ("└── " if is_last else "├── ")
        print(prefix + d)
