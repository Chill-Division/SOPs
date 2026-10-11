#!/usr/bin/env python3
"""
One-off structural normalizer for Google-Docs-exported SOP Markdown.

The export indents numbered list items inconsistently (the same logical level
appears at 3 and 4 spaces; sub-levels at 6/7/8; etc.), which makes CommonMark
mis-nest sibling items. Indentation width alone is ambiguous, so this script
re-levels items using NUMBER CONTINUITY: an item whose number continues an
ancestor's sequence (n == ancestor.last + 1) is a sibling of that ancestor;
an item numbered 1 that is more indented than the current item starts a new
child list. Marker lines are re-emitted at a clean 4-spaces-per-level indent;
continuation lines (prose, code, tables) are shifted by the same delta as their
governing marker so relative indentation (e.g. the VPD lambda) is preserved.

Usage: python3 publish/normalize_lists.py <file.md> [--out <file.md>]
"""
import argparse
import re
import sys

MARKER_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
INDENT_PER_LEVEL = 4


def normalize(text: str) -> str:
    lines = text.split("\n")
    out = []
    # stack of dicts: {"old": old_indent, "last": last_number, "level": level}
    stack = []
    cur_delta = 0  # indentation delta applied to the current marker's block

    for line in lines:
        m = MARKER_RE.match(line)
        if not m:
            # continuation / prose / code / blank: shift by current block delta
            if line.strip() == "":
                out.append("")
            elif cur_delta:
                if cur_delta > 0:
                    out.append(" " * cur_delta + line)
                else:  # dedent, but never past column 0
                    strip = min(len(line) - len(line.lstrip(" ")), -cur_delta)
                    out.append(line[strip:])
            else:
                out.append(line)
            continue

        old_indent = len(m.group(1))
        num = int(m.group(2))
        body = m.group(3)

        # Pop levels that are more indented than this item (a dedent).
        while stack and old_indent < stack[-1]["old"]:
            stack.pop()

        # Find the deepest open level whose sequence this number continues.
        cont_level = None
        for i in range(len(stack) - 1, -1, -1):
            if stack[i]["last"] + 1 == num and old_indent >= stack[i]["old"] - 1:
                cont_level = i
                break

        if cont_level is not None:
            del stack[cont_level + 1:]
            stack[cont_level].update(old=old_indent, last=num)
            level = stack[cont_level]["level"]
        elif num == 1:
            # New child list (or first top-level item of a section).
            level = stack[-1]["level"] + 1 if stack else 0
            stack.append({"old": old_indent, "last": num, "level": level})
        elif stack:
            # Non-continuing, non-1: treat as sibling of nearest shallower level.
            while stack and old_indent < stack[-1]["old"]:
                stack.pop()
            if stack:
                stack[-1].update(old=old_indent, last=num)
                level = stack[-1]["level"]
            else:
                level = 0
                stack.append({"old": old_indent, "last": num, "level": 0})
        else:
            level = 0
            stack.append({"old": old_indent, "last": num, "level": 0})

        new_indent = level * INDENT_PER_LEVEL
        cur_delta = new_indent - old_indent
        out.append(" " * new_indent + f"{num}. {body}")

    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out")
    args = ap.parse_args()
    text = open(args.path, encoding="utf-8").read()
    result = normalize(text)
    dest = args.out or args.path
    open(dest, "w", encoding="utf-8").write(result)
    print(f"normalized -> {dest}")


if __name__ == "__main__":
    main()
