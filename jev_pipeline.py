"""Entrypoint to run the JEV evaluation pipeline from project root."""

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent
code_dir = root_dir / "code"

if str(code_dir) not in sys.path:
    sys.path.insert(0, str(code_dir))
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from code.jev_pipeline import main, run_pipeline

if __name__ == "__main__":
    main()
