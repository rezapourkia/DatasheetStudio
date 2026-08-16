"""Export-only helper: copy a real DipTrace plug-in exchange without modifying it."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import shutil
import sys
import tempfile


def capture_roots() -> list[Path]:
    roots: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(Path(local) / "DipTrace" / "PluginCaptures")
    roots.append(Path(tempfile.gettempdir()) / "DipTrace" / "PluginCaptures")
    return roots


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return 2
    source = Path(argv[1]).resolve()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    for folder in capture_roots():
        try:
            folder.mkdir(parents=True, exist_ok=True)
            destination = folder / f"plugin_exchange-{stamp}.xml"
            shutil.copyfile(source, destination)
            # Never write, touch, rename, or replace source: ImpMode must be None.
            return 0
        except OSError:
            continue
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
