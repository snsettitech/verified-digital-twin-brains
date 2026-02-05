import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / 'artifacts' / 'context' / 'repo_map.txt'

SKIP_DIRS = {
    '.git', 'node_modules', '__pycache__', '.model_cache', 'artifacts', 'proof', '.next', 'dist', 'build'
}

MAX_DIRS = 200


def walk_dir(base: Path, depth: int, max_depth: int, lines: list[str]):
    if depth > max_depth:
        return
    try:
        entries = sorted(base.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return
    for entry in entries:
        if entry.name in SKIP_DIRS:
            continue
        prefix = '  ' * depth
        if entry.is_dir():
            lines.append(f"{prefix}{entry.name}/")
            walk_dir(entry, depth + 1, max_depth, lines)
        else:
            lines.append(f"{prefix}{entry.name}")
        if len(lines) >= MAX_DIRS:
            lines.append('...')
            return


def main():
    lines: list[str] = []
    lines.append('Repo Map (depth=2)')
    lines.append('')
    walk_dir(REPO_ROOT, 0, 2, lines)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    main()
