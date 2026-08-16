"""Launcher script for Datasheet Studio."""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from datasheet_studio.app import main

if __name__ == "__main__":
    sys.exit(main())
