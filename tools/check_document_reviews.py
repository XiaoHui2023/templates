from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def run(root: Path, *args: str) -> bytes:
    """Read a Git snapshot without executing project content."""
    return subprocess.check_output(['git', *args], cwd=root)


def check(root: Path, staged: bool) -> int:
    """Require current element reviews before accepting document changes.

    Args:
        root: Repository owning the document review policy.
        staged: Check the index, rejecting differences from reviewed working files.

    Returns:
        A nonzero status if coverage, review identity or a child check fails.
    """
    changes = run(root, 'diff', '--cached', '--name-only', '-z').split(b'\0')
    if not staged:
        changes += run(root, 'diff', '--name-only', '-z').split(b'\0')
        changes += run(root, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0')
    names = {item.decode('utf-8') for item in changes if item}
    documents = {name for name in names if name.startswith('src/') and name.endswith('.md')}
    policy_path = root / '.cursor/skills/project-document-review/policy.json'
    if not policy_path.is_file():
        if documents:
            print('document review policy missing; prepare project Skill reviews before submission')
            return 1
        return 0
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    missing = documents - policy['documents'].keys()
    if missing:
        print(f'documents without element reviews: {sorted(missing)}')
        return 1
    if staged:
        protected = set(policy['documents'])
        for entry in policy['documents'].values():
            review = json.loads((root / entry['review']).read_text(encoding='utf-8'))
            protected.update(review.get('staged_assets', {}))
        for name in names & protected:
            path = (root / name).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                print(f'deleted or unsafe reviewed artifact: {name}')
                return 1
            if run(root, 'rev-parse', ':' + name).strip() != run(root, 'hash-object', '--path=' + name, name).strip():
                print(f'index differs from reviewed file: {name}')
                return 1
    relevant = set(documents)
    for target, entry in policy['documents'].items():
        review = json.loads((root / entry['review']).read_text(encoding='utf-8'))
        if names & (set(review.get('staged_assets', {})) | set(review.get('sources', {}))):
            relevant.add(target)
    for target in sorted(relevant):
        entry = policy['documents'][target]
        command = [policy['python'], policy['checker'], 'check', '--root', str(root),
                   '--draft', entry['draft'], '--target', target, '--review', entry['review'],
                   '--vocabulary', policy['vocabulary']]
        if entry.get('assurance_profile'):
            command += ['--assurance-profile', entry['assurance_profile']]
        result = subprocess.run(command, cwd=root)
        if result.returncode:
            return result.returncode
    return 0


def main() -> int:
    """Validate the current or staged repository through the project review policy."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--staged', action='store_true')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    return check(args.root.resolve(), args.staged)


if __name__ == '__main__':
    raise SystemExit(main())
