"""Recover only the fresh CP73 slot using the original CONTROL primitive."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    spec = importlib.util.spec_from_file_location('_cp73_restore', HERE / 'root-control.py')
    root = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(root)
    root.restore_control()
    print('CP73_RESTORE_EXECUTED')


if __name__ == '__main__':
    main()
