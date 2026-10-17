"""Default entry point installed at the desktop companion's root directory."""
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    application = Path(__file__).resolve().parent / 'codex-pet'
    sys.path.insert(0, str(application))
    runpy.run_path(str(application / 'main.py'), run_name='__main__')
