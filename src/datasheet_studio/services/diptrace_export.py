"""DipTrace Component Editor (`.elixml`) library export.

Turns the pinout rows extracted from *any* datasheet (see
``PdfReader.get_all_pinouts``) into a self-contained DipTrace component
library file containing one schematic symbol for the selected package.

The generated file follows the DipTrace XML conventions documented in
``docs/diptrace/`` (Component Editor dialect, 5.x library format). The
symbol is a plain ``Free``-template box: pins on the left and right sides, a
rectangle body, and ``Name``/``Value`` text. No physical footprint (pattern)
is attached — a datasheet pinout table does not describe the land pattern
geometry, so a footprint must be assigned inside DipTrace afterwards.
"""

from __future__ import annotations

import hashlib
import re
from xml.sax.saxutils import escape

# ---------------------------------------------------------------------------
# Layout constants (units: mil)
# ---------------------------------------------------------------------------

PIN_PITCH = 100.0  # vertical distance between pin rows
PIN_LENGTH = 100.0  # pin stub length outside the body
MIN_BODY_HALF_WIDTH = 200.0
MIN_SYMBOL_HEIGHT = 300.0
NAME_TEXT_GAP = 60.0  # name text above the body
VALUE_TEXT_GAP = 60.0  # value text below the body
PIN_NAME_FONT_SIZE = 4
PART_TEXT_FONT_SIZE = 5

# Text placement nudges relative to each pin's connection point (the free end).
# The reference DipTrace layout keeps signal *names* away from the pin row and
# pin *numbers* near the pin on the same side, with both labels mirrored per
# orientation.
_NAME_OUTSET = 55.0
_NUM_OUTSET = 40.0

_POWER_PIN_TOKENS = {
    "VDD", "VSS", "VCC", "VEE", "GND", "AVDD", "AVSS", "DVDD", "DVSS",
    "VDDA", "VSSA", "VDDIO", "VSSIO", "VDDH", "VDDL", "VBAT", "VREF",
    "VREF+", "VREF-", "VBUS", "VIN", "VOUT", "VREG", "VCAP", "VBATT",
    "BAT", "BATT", "PWR", "VPWR", "VPRE",
}
_POWER_PREFIXES = ("VDD", "VSS", "VCC", "VEE", "AVDD", "AVSS", "DVDD", "DVSS")
_POWER_SUFFIXES = ("GND", "GNDA", "GNDD", "GNDP")
_RESET_TOKENS = {"NRST", "RESET", "RST", "RESETN", "MR"}

_XML_ATTRIBUTE_ESCAPES = {'"': "&quot;"}
_PIN_NUMBER_TOKEN_RE = re.compile(r"^[A-Za-z]{1,3}\d{1,3}$|^\d{1,4}$")
_PIN_NUMBER_RANGE_RE = re.compile(r"^(\d{1,4})\s*-\s*(\d{1,4})$")


def sanitize_name(text: str, fallback: str = "IC") -> str:
    """Turn a free-text name into a safe filename/library token.

    Non-alphanumeric runs become a single underscore; empty results fall back
    to ``fallback``.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_+.-]", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).replace(" ", "_")
    cleaned = re.sub(r"_+", "_", cleaned).strip("_.-")
    return cleaned or fallback


def short_pin_name(pin_name: str, max_len: int = 10) -> str:
    """Shorten a datasheet pin name for on-symbol display.

    Datasheet pin tables often carry verbose names such as
    ``PC14- OSC32 IN`` or ``PB8-BOOT0``; a schematic symbol should show the
    short base name instead (``PC14``, ``PB8``). Names without a base-part
    separator (``VBAT``, ``VREF+``, ``OSC_IN``) are kept as-is.
    """
    if not pin_name:
        return ""
    text = str(pin_name).strip()
    base = re.split(r"[\-/(]", text, maxsplit=1)[0].strip()
    base = re.sub(r"\s+", " ", base).strip()
    if not base:
        base = text.split()[0] if text.split() else text
    return base[:max_len]


def pin_electric_type(pin_name: str) -> str:
    """Best-effort ERC electric type for a pin name.

    Power pins (VDD/VSS/VCC/GND/... variants) become ``Power``, reset pins
    become ``Input``, everything else stays ``Undefined``.
    """
    if not pin_name:
        return "Undefined"
    token = re.split(r"[\s\-_/\\]+", str(pin_name).strip())[0].upper()
    token = re.sub(r"[^A-Z0-9+]", "", token)
    if token in _RESET_TOKENS:
        return "Input"
    if token in _POWER_PIN_TOKENS:
        return "Power"
    if any(token.startswith(prefix) for prefix in _POWER_PREFIXES):
        return "Power"
    if any(token.endswith(suffix) for suffix in _POWER_SUFFIXES):
        return "Power"
    return "Undefined"


#: Manufacturer/part-number prefixes used to name generated symbols.
#: Underscores are treated as separators (not word characters) so file names
#: like ``1324_MAX17201-MAX17215_1-2.pdf`` still yield ``MAX17201``.
_IC_PATTERN = re.compile(
    r"(?i)(?<![A-Za-z0-9+])((?:STM32|STM8|ATSAM|ATMEGA|ATTINY|AT89|MAX|BQ|AD|LT|LTC|LP|"
    r"TPS|TUSB|LM|DRV|INA|FDC|UCC|IRF|PCA|MCP|MSP430|CC25|CC26|ESP32|"
    r"ESP8266|nRF52|TLE|AUIR|MC9S|MK[0-9])[A-Z0-9+]{2,20})(?![A-Za-z0-9+])"
)


def extract_part_number(text: str) -> str:
    """Return a plausible component part number found in ``text``, else ``""``.

    Used to name generated symbols. Candidates must contain a digit (part
    numbers almost always do, which rejects words such as ``MAXIMUM`` or
    ``ADAPTER``) and datasheet wildcard suffixes such as ``zzzz``/``xxx`` are
    trimmed (``STM32G431zzzz`` -> ``STM32G431``).
    """
    match = _IC_PATTERN.search(text or "")
    if not match:
        return ""
    token = match.group(1).upper()
    if not re.search(r"\d", token):
        return ""
    token = re.sub(r"[ZX]{2,}$", "", token)
    return token or ""


def _make_uid(seed: str) -> int:
    """Stable positive 32-bit library UID derived from the component name."""
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    value = int.from_bytes(digest[:4], "big") % (2**31 - 1)
    return value or 1


def _fmt(value: float) -> str:
    """Format a coordinate/length as a short dot-decimal number."""
    return format(float(value), "g")


def _esc_attr(value) -> str:
    return escape(str(value), _XML_ATTRIBUTE_ESCAPES)


def _esc_text(value) -> str:
    return escape(str(value))


def _layout_pins(pin_rows) -> tuple[list[tuple[float, float, str]], float, int, float]:
    """Compute pin coordinates for a two-sided box symbol.

    Pins 1..ceil(N/2) run top-to-bottom on the left side; the remaining pins
    run bottom-to-top on the right side (counter-clockwise numbering).
    Returns ``(coords, symbol_height, pins_per_side, body_half_width)`` where
    each coord is ``(x, y, orientation)`` in mil and the pin's free
    (connection) end is at ``(x, y)``.

    DipTrace draws the pin stub *in the direction of ``Orientation``* from
    the pin point: a left pin must therefore point right (``"0"``) so its
    stub reaches the body, and a right pin must point left (``"180"``).
    """
    pin_count = len(pin_rows)
    left_count = (pin_count + 1) // 2
    right_count = pin_count - left_count
    pins_per_side = max(left_count, right_count)
    height = max(pins_per_side * PIN_PITCH, MIN_SYMBOL_HEIGHT)

    body_half_width = float(MIN_BODY_HALF_WIDTH)
    # Keep symbol edges on DipTrace's common 50-mil drawing grid.
    body_half_width = float(int((body_half_width + 49.0) // 50.0) * 50)
    tip_x = body_half_width + PIN_LENGTH

    coords: list[tuple[float, float, str]] = []
    for i in range(pin_count):
        if i < left_count:
            y = height / 2.0 - (i + 0.5) * PIN_PITCH
            coords.append((-tip_x, y, "0"))
        else:
            j = i - left_count
            y = -height / 2.0 + (j + 0.5) * PIN_PITCH
            coords.append((tip_x, y, "180"))
    return coords, height, pins_per_side, body_half_width


def _normalize_rows(pin_rows) -> list[dict]:
    """Coerce extracted rows into the ``{pin, name}`` shape the writer needs."""
    normalized: list[dict] = []
    for index, row in enumerate(pin_rows):
        if not isinstance(row, dict):
            row = {"pin": row, "name": str(row)}
        pin_number = str(row.get("pin", "")).strip()
        pin_name = str(row.get("name", "")).strip()
        if not pin_number:
            pin_number = str(index + 1)
        normalized.append({"pin": pin_number, "name": pin_name})
    return normalized


def _pin_number_sort_key(value: str) -> tuple[int, int | str]:
    """Sort numeric pin numbers before alphanumeric ball identifiers."""
    value = str(value).strip()
    if value.isdigit():
        return (0, int(value))
    return (1, value.upper())


def expand_pin_numbers(pin_rows) -> list[dict]:
    """Expand numeric pin ranges/lists into one row per physical pin.

    Datasheets commonly describe tied pads as one logical signal, for example
    ``VBUS | 2-3``.  A DipTrace symbol needs one pin record for each physical
    pad, so this turns that row into pin 2 and pin 3 while retaining all other
    information. Alphanumeric ball identifiers are left unchanged.
    """
    expanded: list[dict] = []
    for row in _normalize_rows(pin_rows):
        token = row["pin"].replace(" ", "")
        parts = token.split(",") if "," in token else [token]
        numbers: list[str] = []
        for part in parts:
            match = _PIN_NUMBER_RANGE_RE.match(part)
            if match:
                start, end = (int(match.group(1)), int(match.group(2)))
                if start <= end:
                    numbers.extend(str(number) for number in range(start, end + 1))
                    continue
            numbers.append(part)
        for number in numbers:
            clone = dict(row)
            clone["pin"] = number
            expanded.append(clone)
    return expanded


def validate_pin_rows(pin_rows, expected_pin_count: int | None = None) -> tuple[list[dict], list[str]]:
    """Return normalized physical pin rows and any safety errors.

    A generated symbol must never silently contain duplicate, malformed, or
    incomplete physical pin numbers.  ``expected_pin_count`` comes from a
    package label such as ``LQFP48`` when available.
    """
    rows = expand_pin_numbers(pin_rows)
    errors: list[str] = []
    seen: set[str] = set()
    for row in rows:
        pin = row["pin"].strip()
        if not _PIN_NUMBER_TOKEN_RE.fullmatch(pin):
            errors.append(f"Unsupported pin number: {pin or '(empty)'}")
            continue
        key = pin.upper()
        if key in seen:
            errors.append(f"Duplicate physical pin: {pin}")
        seen.add(key)
        if not row["name"].strip():
            errors.append(f"Pin {pin} has no name")

    if expected_pin_count is not None and expected_pin_count > 0 and len(seen) != expected_pin_count:
        errors.append(
            f"Package expects {expected_pin_count} physical pins, but the table contains {len(seen)}"
        )

    rows.sort(key=lambda row: _pin_number_sort_key(row["pin"]))
    return rows, errors


def build_component_library(
    pin_rows,
    *,
    component_name: str,
    package: str = "",
    value: str = "",
    refdes: str = "U",
    manufacturer: str = "",
    library_name: str = "",
    hint: str = "",
    units: str = "mil",
    version: str = "5.3.0.0",
    expected_pin_count: int | None = None,
) -> str:
    """Build a complete DipTrace component-library (``.elixml``) text.

    ``pin_rows`` is a list of dicts with ``pin`` (datasheet pin number, e.g.
    ``"1"`` or ``"A1"``) and ``name`` (pin name). Returns the full library
    XML as a string, ready to be saved as ``*.elixml`` and opened in DipTrace
    Component Editor.
    """
    rows, validation_errors = validate_pin_rows(pin_rows, expected_pin_count)
    if not rows:
        raise ValueError("No pins to build a symbol from.")
    if validation_errors:
        raise ValueError("Pin table needs review: " + "; ".join(validation_errors))
    if not component_name or not str(component_name).strip():
        raise ValueError("component_name is required.")

    component_name = str(component_name).strip()
    package = str(package or "").strip()
    value = str(value or "").strip() or component_name
    refdes = str(refdes or "").strip() or "U"
    manufacturer = str(manufacturer or "").strip()

    library_name = str(library_name or "").strip()
    if not library_name:
        library_name = f"{component_name} {package}".strip()
    hint = str(hint or "").strip() or library_name

    coords, height, _pins_per_side, body_half_width = _layout_pins(rows)
    width = 2.0 * body_half_width
    top = height / 2.0
    uid = _make_uid(library_name)

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<Library Type="DipTrace-ComponentLibrary" Name="{_esc_attr(library_name)}" '
        f'Hint="{_esc_attr(hint)}" Version="{_esc_attr(version)}" '
        f'UID32="{uid}" Units="{_esc_attr(units)}">'
    )
    lines.append("  <Components>")
    lines.append('    <Component Id="0">')
    lines.append(
        f'      <Part Id="0" RefDes="{_esc_attr(refdes)}" PartType="Normal" '
        f'ShowNumbers="Show" Type="Free" Int1="0" Int2="0" '
        f'Width="{_fmt(width)}" Height="{_fmt(height)}" '
        f'LockTypeChange="Y" SubFolderIndex="0">'
    )
    lines.append(f"        <Name>{_esc_text(component_name)}</Name>")
    lines.append("        <PartName>Part 1</PartName>")
    lines.append(f"        <Value>{_esc_text(value)}</Value>")
    lines.append('        <Origin X="0" Y="0"/>')
    if manufacturer:
        lines.append(f"        <Manufacturer>{_esc_text(manufacturer)}</Manufacturer>")

    lines.append("        <Pins>")
    for index, ((x, y, orientation), row) in enumerate(zip(coords, rows)):
        electric = pin_electric_type(row["name"])
        if orientation == "0":
            num_shift, name_shift = _NUM_OUTSET, -_NAME_OUTSET
        else:
            num_shift, name_shift = -_NUM_OUTSET, _NAME_OUTSET
        lines.append(
            f'          <Pin Id="{index}" X="{_fmt(x)}" Y="{_fmt(y)}" Locked="N" '
            f'Type="Default" ElectricType="{electric}" Orientation="{orientation}" '
            f'PadId="{index}" Length="{_fmt(PIN_LENGTH)}" ShowName="Y" '
            f'NumXShift="{_fmt(num_shift)}" NumYShift="-20" '
            f'NameXShift="{_fmt(name_shift)}" NameYShift="20" SignalDelay="0" '
            f'NumOrientation="0" NameOrientation="0" Group="-1">'
        )
        lines.append(f"            <Name>{_esc_text(short_pin_name(row['name']))}</Name>")
        lines.append(f"            <PadNumber>{_esc_text(row['pin'])}</PadNumber>")
        lines.append(
            f'            <NameFont Size="{PIN_NAME_FONT_SIZE}" '
            f'FontSizeFloat="{PIN_NAME_FONT_SIZE}" '
            'Width="-2" Scale="1" FontMono="N"/>'
        )
        lines.append("          </Pin>")
    lines.append("        </Pins>")

    lines.append("        <Shapes>")
    lines.append(
        '          <Shape Id="0" Type="Rectangle" LineWidth="10" Locked="N" Group="-1">'
    )
    lines.append("            <Points>")
    lines.append(f'              <Point X="{_fmt(-body_half_width)}" Y="{_fmt(top)}"/>')
    lines.append(f'              <Point X="{_fmt(body_half_width)}" Y="{_fmt(-top)}"/>')
    lines.append("            </Points>")
    lines.append("          </Shape>")

    for shape_id, text_show, text_y in (
        (1, "Name", top + NAME_TEXT_GAP),
        (2, "Value", -top - VALUE_TEXT_GAP),
    ):
        lines.append(
            f'          <Shape Id="{shape_id}" Type="Text" Locked="N" '
            f'FontVector="Y" FontMono="N" FontSize="{PART_TEXT_FONT_SIZE}" '
            f'FontSizeFloat="{PART_TEXT_FONT_SIZE}" '
            f'FontColor="0" TextShow="{text_show}" FontName="" FontWidth="-2" '
            f'FontScale="1" Angle="0" HorzAlign="Center" VertAlign="Center" '
            f'TextAlign="Center" LineSpacing="1.2" Group="-1">'
        )
        lines.append("            <Points>")
        lines.append(f'              <Point X="0" Y="{_fmt(text_y)}"/>')
        lines.append("            </Points>")
        lines.append("          </Shape>")
    lines.append("        </Shapes>")

    lines.append("      </Part>")
    lines.append("    </Component>")
    lines.append("  </Components>")
    lines.append("</Library>")
    return "\n".join(lines) + "\n"
