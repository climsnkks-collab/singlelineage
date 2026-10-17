"""Integration-main only: command-zero details-spawn with one entry write watch."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from tools.local_original_session import launcher, entry_watch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_name')
    parser.add_argument('--product', choices=entry_watch.known_products(launcher),
                        default='sibling-internal-lifecycle-details-spawn')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]{1,64}', args.run_name):
        parser.error('FRESH_BOUNDED_RUN_NAME_REQUIRED')
    directory = ROOT / 'work/local_original_session/runs' / args.run_name
    # No test duration, command poster, scene stop, Quit, or close.request writer.
    previous = sys.argv
    sys.argv = ['launcher', '--run', '--control-mode', 'internal',
                '--product', args.product,
                '--image', str(ROOT / 'work/standalone_boot/current-unmodified-clone/LC.guard.exe'),
                '--expected-uuid', 'a1416ea8-d0e1-4b93-b622-c27752ef6b51',
                '--store', str(ROOT / 'work/local_original_session/test-profile/characters.json'),
                '--run-directory', str(directory)]
    try:
        with entry_watch.installed(launcher, directory):
            return launcher.main()
    finally:
        sys.argv = previous


if __name__ == '__main__':
    raise SystemExit(main())
