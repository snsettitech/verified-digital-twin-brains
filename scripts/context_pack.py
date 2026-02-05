import subprocess
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / 'artifacts' / 'context' / 'context_pack.md'

KEY_FILES = [
    'CRITICAL_PATH_CALL_GRAPH.md',
    'CRITICAL_PATH_CONTRACT_MATRIX.md',
    'FE_BE_DRIFT_REPORT.md',
    'INGESTION_PROOF_PACKET.md',
    'PUBLIC_RETRIEVAL_PROOF_PACKET.md',
    'PHASE_D_FINAL_PROOF.md',
    'docs/CDR-001-canonical-contracts.md',
    'SCOPE_CUT_PROPOSAL.md',
    'SIMPLIFICATION_CHANGELOG.md',
    'proof/PROOF_README.md'
]

MAX_CHARS = 4000


def read_snippet(path: Path) -> str:
    if not path.exists():
        return '(missing)'
    text = path.read_text(encoding='utf-8', errors='ignore')
    if len(text) <= MAX_CHARS:
        return text
    return text[:MAX_CHARS] + '\n...\n'


def safe_run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            return result.stderr.strip() or result.stdout.strip()
        return result.stdout.strip()
    except Exception as exc:
        return f'error: {exc}'


def main():
    lines: list[str] = []
    lines.append('# Context Pack')
    lines.append('')
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append('')

    lines.append('## Repo Status')
    lines.append('```')
    lines.append(safe_run(['git', 'status', '-sb']))
    lines.append('```')
    lines.append('')

    lines.append('## Repo Map')
    lines.append('```')
    lines.append(safe_run(['python', 'scripts/repo_map.py']) or '(generated)')
    try:
        repo_map_path = REPO_ROOT / 'artifacts' / 'context' / 'repo_map.txt'
        if repo_map_path.exists():
            lines.append(repo_map_path.read_text(encoding='utf-8', errors='ignore'))
    except Exception:
        lines.append('(repo map unavailable)')
    lines.append('```')
    lines.append('')

    lines.append('## Key Docs')
    for rel in KEY_FILES:
        path = REPO_ROOT / rel
        lines.append(f"### {rel}")
        lines.append('```')
        lines.append(read_snippet(path))
        lines.append('```')
        lines.append('')

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    main()
