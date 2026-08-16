"""Production-safe DipTrace plug-in entry point.

Implement transform(root) so it changes the in-memory tree and returns True only
when a semantic edit should be imported. Keep this wrapper unchanged where possible.
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET


PLUGIN_NAME = "MyPlugin"
PLUGIN_VERSION = "0.1.0"
# Replace with exactly one tested data-root Type, for example:
# {"DipTrace-PCB"}, {"DipTrace-Schematic"}, {"DipTrace-ComponentLibrary"},
# or {"DipTrace-PatternLibrary"}. Empty means the template is not configured.
EXPECTED_ROOT_TYPES: set[str] = set()


def parse_finite_real(raw: str, *, object_name: str, attribute: str) -> float:
    """Accept legacy comma input, but reject missing and non-finite geometry."""
    try:
        value = float(raw.replace(",", "."))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{object_name}: invalid {attribute}={raw!r}") from exc
    if not math.isfinite(value):
        raise ValueError(f"{object_name}: non-finite {attribute}={raw!r}")
    return value


def format_real(value: float, digits: int = 4) -> str:
    """Return deterministic dot-decimal text and normalize negative zero."""
    if not math.isfinite(value):
        raise ValueError(f"cannot serialize non-finite value {value!r}")
    rounded = round(value, digits)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{digits}f}".rstrip("0").rstrip(".") or "0"


def transform(root: ET.Element) -> bool:
    """Validate, analyze, and make semantic edits. Return True iff changed."""
    del root
    # TODO: implement. Keep analysis broad and construct a narrow Edit result.
    return False


def log_candidates() -> list[Path]:
    candidates: list[Path] = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(Path(local) / "DipTrace" / "PluginLogs")
    candidates.append(Path(tempfile.gettempdir()) / "DipTrace" / "PluginLogs")
    return candidates


def write_log(message: str) -> Path | None:
    for folder in log_candidates():
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{PLUGIN_NAME}.log"
            path.write_text(message, encoding="utf-8")
            return path
        except OSError:
            continue
    return None


def atomic_write(tree: ET.ElementTree, exchange_path: Path) -> None:
    fd, raw_temp = tempfile.mkstemp(
        prefix="plugin_exchange.", suffix=".tmp", dir=exchange_path.parent
    )
    os.close(fd)
    temp_path = Path(raw_temp)
    try:
        tree.write(temp_path, encoding="utf-8", xml_declaration=True)
        # Reparse before commit so a serializer/disk failure cannot replace the input.
        ET.parse(temp_path)
        os.replace(temp_path, exchange_path)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def run(exchange_path: Path) -> bool:
    tree = ET.parse(exchange_path)
    root = tree.getroot()
    if not EXPECTED_ROOT_TYPES:
        raise RuntimeError("configure EXPECTED_ROOT_TYPES before building")
    actual_type = root.get("Type")
    if actual_type not in EXPECTED_ROOT_TYPES:
        raise ValueError(f"unsupported root Type={actual_type!r}")
    changed = transform(root)
    if not changed:
        return False
    atomic_write(tree, exchange_path)
    return True


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        write_log(
            f"{PLUGIN_NAME} {PLUGIN_VERSION}\n"
            "Expected exactly one DipTrace exchange-file argument.\n"
        )
        return 2
    exchange_path = Path(argv[1]).resolve()
    try:
        run(exchange_path)
        return 0
    except Exception:
        # DipTrace hard termination cannot run Python cleanup; atomic replacement
        # still protects the original, while an orphan .tmp may remain.
        write_log(
            f"{PLUGIN_NAME} {PLUGIN_VERSION}\n"
            f"Exchange: {exchange_path}\n\n{traceback.format_exc()}"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
