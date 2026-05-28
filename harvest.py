#!/usr/bin/env python3
import argparse
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

TAGS = ["TODO", "FIXME", "HACK", "XXX", "NOTE"]

TAG_COLORS = {
    "TODO":  "\033[1;33m",
    "FIXME": "\033[1;31m",
    "HACK":  "\033[1;35m",
    "XXX":   "\033[1;31m",
    "NOTE":  "\033[1;36m",
}
RESET = "\033[0m"
DIM   = "\033[2m"

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__",
    ".cache", "dist", "build", "target", ".venv", "venv",
}


@dataclass
class LangConfig:
    line_prefixes: list
    block_opens: list        # possible block-open tokens, longest first
    block_close_map: dict    # open-token -> close-token


LANG_CONFIG = {
    ".py":  LangConfig(["#"],  ['"""', "'''"], {'"""': '"""', "'''": "'''"}),
    ".js":  LangConfig(["//"], ["/*"],          {"/*": "*/"}),
    ".ts":  LangConfig(["//"], ["/*"],          {"/*": "*/"}),
    ".c":   LangConfig(["//"], ["/*"],          {"/*": "*/"}),
    ".cpp": LangConfig(["//"], ["/*"],          {"/*": "*/"}),
    ".h":   LangConfig(["//"], ["/*"],          {"/*": "*/"}),
    ".rs":  LangConfig(["//"], ["/*"],          {"/*": "*/"}),
    ".go":  LangConfig(["//"], ["/*"],          {"/*": "*/"}),
    ".sh":  LangConfig(["#"],  [],              {}),
    ".rb":  LangConfig(["#"],  [],              {}),
    ".lua": LangConfig(["--"], ["--[["],        {"--[[": "]]"}),
}


@dataclass
class Match:
    file: str
    line_no: int
    tag: str
    content: str


def find_tag(text: str) -> Optional[str]:
    upper = text.upper()
    for tag in TAGS:
        if tag in upper:
            return tag
    return None


def scan_file(path: str, lang: LangConfig) -> list:
    matches = []
    try:
        with open(path, encoding="utf-8", errors="strict") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        return []
    except PermissionError:
        print(f"{DIM}warning: cannot read {path}{RESET}", file=sys.stderr)
        return []

    in_block = False
    block_close = None

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        comment_text = None

        if in_block:
            if block_close in line:
                idx = line.index(block_close)
                comment_text = line[:idx]
                in_block = False
                block_close = None
            else:
                comment_text = line
        else:
            # Check for line comment first — takes priority over block openers
            # But only if no block opener matches at the same position
            found_line_comment = False
            for prefix in lang.line_prefixes:
                idx = stripped.find(prefix)
                if idx != -1:
                    # Check if a block opener also starts at position 0
                    # (these take priority over line comments)
                    block_opener_at_start = False
                    for opener in lang.block_opens:
                        if stripped.startswith(opener):
                            block_opener_at_start = True
                            break

                    if not block_opener_at_start:
                        comment_text = stripped[idx + len(prefix):]
                        found_line_comment = True
                        break

            # Check for block comment open only if no line comment on this line
            if not found_line_comment:
                for opener in lang.block_opens:
                    # For triple-quote openers, only match at start of stripped line
                    if len(opener) == 3 and opener[0] == opener[1] == opener[2]:
                        matches_here = stripped.startswith(opener)
                    else:
                        matches_here = opener in line
                    if matches_here:
                        if len(opener) == 3 and opener[0] == opener[1] == opener[2]:
                            open_idx = 0
                            rest = stripped[len(opener):]
                        else:
                            open_idx = line.index(opener)
                            rest = line[open_idx + len(opener):]
                        closer = lang.block_close_map[opener]
                        if closer in rest:
                            # opens and closes on the same line
                            close_idx = rest.index(closer)
                            comment_text = rest[:close_idx]
                        else:
                            in_block = True
                            block_close = closer
                            comment_text = rest
                        break

        if comment_text:
            tag = find_tag(comment_text)
            if tag:
                matches.append(Match(
                    file=path,
                    line_no=lineno,
                    tag=tag,
                    content=stripped,
                ))

    return matches


def scan_dir(root: str, tag_filter: Optional[str] = None) -> list:
    all_matches = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in LANG_CONFIG:
                continue
            fpath = os.path.join(dirpath, fname)
            lang = LANG_CONFIG[ext]
            matches = scan_file(fpath, lang)
            if tag_filter:
                matches = [m for m in matches if m.tag == tag_filter.upper()]
            all_matches.extend(matches)
    return all_matches


def _group_by_tag(matches: list) -> dict:
    groups = {tag: [] for tag in TAGS}
    for m in matches:
        groups[m.tag].append(m)
    return {tag: lst for tag, lst in groups.items() if lst}


def _format_match_line(m: Match, root: str, use_color: bool) -> str:
    try:
        rel = os.path.relpath(m.file, root)
    except ValueError:
        rel = m.file
    loc = f"{rel}:{m.line_no}"
    if use_color:
        return f"  {DIM}{loc:<40}{RESET}  {m.content}"
    return f"  {loc:<40}  {m.content}"


def render_terminal(matches: list, root: str) -> None:
    groups = _group_by_tag(matches)
    if not groups:
        print("No annotations found.")
        return
    for tag in TAGS:
        if tag not in groups:
            continue
        items = sorted(groups[tag], key=lambda m: (m.file, m.line_no))
        color = TAG_COLORS[tag]
        bar = "━" * max(0, 38 - len(tag) - len(str(len(items))))
        print(f"{color}━━━ {tag} ({len(items)}) {bar}{RESET}")
        for m in items:
            print(_format_match_line(m, root, use_color=True))
        print()


def render_file(matches: list, root: str, output_path: str) -> None:
    groups = _group_by_tag(matches)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            if not groups:
                f.write("No annotations found.\n")
                return
            for tag in TAGS:
                if tag not in groups:
                    continue
                items = sorted(groups[tag], key=lambda m: (m.file, m.line_no))
                bar = "━" * max(0, 38 - len(tag) - len(str(len(items))))
                f.write(f"━━━ {tag} ({len(items)}) {bar}\n")
                for m in items:
                    f.write(_format_match_line(m, root, use_color=False) + "\n")
                f.write("\n")
    except OSError as e:
        print(f"error: cannot write to {output_path}: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan source files for TODO/FIXME/HACK/XXX/NOTE comments.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--path", default=os.getcwd(),
        metavar="DIR",
        help="Directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--type", dest="tag_filter", metavar="TAG",
        help=f"Show only this tag (case-insensitive): {', '.join(TAGS)}",
    )
    parser.add_argument(
        "--output", metavar="FILE",
        help="Write plain-text report to this file",
    )
    args = parser.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(f"error: '{root}' is not a directory", file=sys.stderr)
        sys.exit(1)

    tag_filter = None
    if args.tag_filter:
        tag_filter = args.tag_filter.upper()
        if tag_filter not in TAGS:
            parser.error(f"--type must be one of: {', '.join(TAGS)}")

    matches = scan_dir(root, tag_filter)
    matches.sort(key=lambda m: (m.tag, m.file, m.line_no))

    render_terminal(matches, root)

    if args.output:
        render_file(matches, root, args.output)
        print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
