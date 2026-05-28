# harvest

Scan your codebase for `TODO`, `FIXME`, `HACK`, `XXX`, and `NOTE` comments. Results are grouped by tag and printed with colored terminal output.

```
━━━ TODO (3) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  src/main.py:42                              # TODO: handle empty input edge case
  src/parser.py:17                            # TODO: add timeout support
  lib/net.c:88                                // TODO: replace with non-blocking I/O

━━━ FIXME (1) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  src/auth.rs:55                              // FIXME: this leaks on panic
```

## Requirements

- Python 3.6+ (stdlib only — no pip installs)
- Linux / macOS

## Installation

```bash
curl -O https://raw.githubusercontent.com/Bugzymp4/harvest/main/harvest.py
chmod +x harvest.py
```

Or clone:

```bash
git clone https://github.com/Bugzymp4/harvest.git
cd harvest
chmod +x harvest.py
```

Optionally move it onto your `$PATH`:

```bash
mv harvest.py ~/.local/bin/harvest
```

## Usage

```bash
# Scan current directory
./harvest.py

# Scan a specific project
./harvest.py --path /path/to/project

# Show only one tag type (case-insensitive)
./harvest.py --path /path/to/project --type todo
./harvest.py --path /path/to/project --type fixme

# Export a plain-text report
./harvest.py --path /path/to/project --output report.txt
```

## Supported Languages

| Language   | Extension     | Line comment | Block comment  |
|------------|---------------|--------------|----------------|
| Python     | `.py`         | `#`          | `"""` `'''`    |
| JavaScript | `.js`         | `//`         | `/* */`        |
| TypeScript | `.ts`         | `//`         | `/* */`        |
| C          | `.c` `.h`     | `//`         | `/* */`        |
| C++        | `.cpp`        | `//`         | `/* */`        |
| Rust       | `.rs`         | `//`         | `/* */`        |
| Go         | `.go`         | `//`         | `/* */`        |
| Shell      | `.sh`         | `#`          | —              |
| Ruby       | `.rb`         | `#`          | —              |
| Lua        | `.lua`        | `--`         | `--[[ ]]`      |

## Tags and Colors

| Tag     | Color   |
|---------|---------|
| `TODO`  | Yellow  |
| `FIXME` | Red     |
| `HACK`  | Magenta |
| `XXX`   | Red     |
| `NOTE`  | Cyan    |

## How It Works

harvest detects keywords **only inside real comment markers** — not inside string literals or arbitrary code. It uses a per-language state machine that tracks single-line prefixes (`#`, `//`, `--`) and block comment delimiters (`/* */`, `"""`, `--[[`), including multi-line blocks and inline comments after code:

```python
x = get_value()  # TODO: validate return type   ← detected
msg = "TODO: not a comment"                      ← ignored
```

Directories automatically skipped: `.git`, `node_modules`, `__pycache__`, `dist`, `build`, `target`, `.venv`, `venv`, `.cache`, `.hg`, `.svn`.

## Running Tests

```bash
python3 -m unittest tests.test_harvest -v
```

35 tests covering single-line comments, block comments (multi-line and same-line), inline-after-code detection, directory pruning, tag filtering, rendering, and CLI behavior.
