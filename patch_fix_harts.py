#!/usr/bin/env python3
"""
Patch script to prevent accidental unconditional `data["hearts"] = 9`
assignments in level files. Creates .bak backups before editing.

Usage: run in the folder with your level files:
    python patch_fix_hearts.py
"""

import glob
import io
import re
import shutil
from pathlib import Path

LEVEL_FILES = sorted(glob.glob("level*.py"))

ASSIGN_PATTERN = re.compile(r'^\s*data\[\s*[\'"]hearts[\'"]\s*\]\s*=\s*9\s*(#.*)?$')

# heuristics: lines upward that indicate correct guarded branch
GUARD_KEYWORDS = [
    r'data\.get\(\s*["\']difficulty["\']\s*\)\s*==\s*["\']hard["\']',
    r'data\[\s*[\'"]hearts[\'"]\s*\]\s*<=\s*0',
    r'data\.get\(\s*[\'"]hearts[\'"]\s*,',
    r'if\s+.*difficulty.*hard',
    r'if\s+.*hearts.*<=\s*0'
]
GUARD_RE = re.compile('|'.join(GUARD_KEYWORDS))

def is_within_guard(lines, assign_index, window=8):
    """
    Heuristic: check `window` lines above the assignment for guard keywords.
    """
    start = max(0, assign_index - window)
    context = "\n".join(lines[start:assign_index+1])
    return bool(GUARD_RE.search(context))

def make_guarded_block(indent):
    """
    Return a string that performs a guarded reset to hearts=9.
    Keep same indentation as the original assignment.
    """
    pad = indent
    block = (
        f"{pad}# guarded reset: only reset to 9 on hard-mode zero to avoid accidental overwrite\n"
        f"{pad}if data.get('difficulty') == 'hard' and int(data.get('hearts', 0)) <= 0:\n"
        f"{pad}    data['highest_completed_seq_index'] = -1\n"
        f"{pad}    data['hearts'] = 9\n"
        f"{pad}    save_progress(data)\n"
        f"{pad}else:\n"
        f"{pad}    # unexpected reset removed to preserve player's remaining hearts\n"
        f"{pad}    pass\n"
    )
    return block

def process_file(path: Path):
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    changed = False
    out_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = ASSIGN_PATTERN.match(line)
        if m:
            # check if there's a guard above
            if is_within_guard(lines, i, window=8):
                out_lines.append(line)
                i += 1
                continue
            # not within guard -> replace this single line with guarded block
            indent_match = re.match(r'^(\s*)', line)
            indent = indent_match.group(1) if indent_match else ''
            out_lines.append(make_guarded_block(indent))
            changed = True
            i += 1
        else:
            out_lines.append(line)
            i += 1

    if changed:
        bak = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, bak)
        path.write_text("\n".join(out_lines) + "\n", encoding='utf-8')
        print(f"[PATCHED] {path} -> backup at {bak}")
    else:
        print(f"[OK] No changes needed: {path}")

def main():
    if not LEVEL_FILES:
        print("No level*.py files found in current directory.")
        return
    for fname in LEVEL_FILES:
        p = Path(fname)
        process_file(p)
    print("Done. Inspect .bak files if you want to revert changes.")

if __name__ == "__main__":
    main()
