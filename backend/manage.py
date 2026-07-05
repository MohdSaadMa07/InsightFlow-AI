#!/usr/bin/env python
import os
import sys
import pathlib

# Ensure the parent of the 'backend/' directory is on sys.path so that
# 'backend' is importable as a package (needed for any backend.* imports).
# The 'backend/' directory itself is already on sys.path when running from it.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
