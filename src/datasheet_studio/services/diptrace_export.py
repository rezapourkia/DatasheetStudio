"""DipTrace Component Editor (`.elixml`) library export.

Turns the pinout rows extracted from *any* datasheet (see
``PdfReader.get_all_pinouts``) into a self-contained DipTrace component
library file containing one schematic symbol for the selected package.

The generated file follows the DipTrace XML conventions documented in
``docs/diptrace/`` (Component Editor dialect, 5.x library format). The
symbol is a plain ``Free``-template box: pins on the left and right sides (and
top/bottom supply pins for small mixed-power symbols), a rectangle body, and
``Name``/``Value`` text. No physical footprint (pattern)
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

# Top/bottom supply-pin layout only applies to small mixed-power symbols;
# larger packages keep the classic two-sided IC box (left/right only).
MIN_VERTICAL_POWER_SYMBOL_PINS = 4
MAX_VERTICAL_POWER_SYMBOL_PINS = 12
MAX_VERTICAL_POWER_PINS = 4

# Text placement nudges relative to each pin's connection point (the free end).
# The reference DipTrace layout (docs/diptrace/captures/probe.elixml) keeps
# signal *names* outside the pin tip and pin *numbers* on the stub near the
# body, with both labels horizontal and mirrored per orientation.
_NAME_OUTSET = 55.0
_NUM_OUTSET = 40.0
# Top/bottom pins: the name label sits beyond the free tip (outside the symbol)
# and the number between tip and body, both horizontal like the side labels.
_TOP_BOTTOM_NAME_OUTSET = 65.0
_TOP_BOTTOM_NUM_OUTSET = 25.0
# Approximate glyph height for the pin-name font size 5
# (5 * 1000 / 76.2 mil, docs/diptrace/02_diptrace_xml_conventions.md).
# Used to keep the part Name/Value text clear of top/bottom pin name labels.
_FONT5_TEXT_HEIGHT = 66.0

_TOP_POWER_TOKENS = {
    "VDD",
    "VCC",
    "VIN",
    "VBUS",
    "VBAT",
    "VREG",
    "VCAP",
    "VOUT",
    "VPWR",
    "VDDIO",
    "VDDH",
    "VDDL",
    "VDDA",
    "AVDD",
    "DVDD",
    "VREF+",
}
_BOTTOM_POWER_TOKENS = {
    "GND",
    "VSS",
    "VSSA",
    "AVSS",
    "DVSS",
    "VSSIO",
    "GNDA",
    "GNDD",
    "GNDP",
    "VEE",
    "VNEG",
    "VREF-",
    "AGND",
    "PGND",
}

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


def _pin_token(pin_name: str) -> str:
    """Return a coarse token used to classify power pins."""
    token = re.split(r"[\s\-_/\\]+", str(pin_name).strip())[0].upper()
    return re.sub(r"[^A-Z0-9+.-]", "", token)


def _is_top_power_pin(pin_name: str) -> bool:
    """Heuristic for supply pins that should sit above the body."""
    token = _pin_token(pin_name)
    return token in _TOP_POWER_TOKENS or any(
        token.startswith(prefix) for prefix in ("VDD", "VCC", "VIN", "VBUS", "VBAT", "VREF+", "VDDA", "AVDD", "DVDD")
    )


def _is_bottom_power_pin(pin_name: str) -> bool:
    """Heuristic for ground / negative supply pins that should sit below the body."""
    token = _pin_token(pin_name)
    return token in _BOTTOM_POWER_TOKENS or any(
        token.startswith(prefix) for prefix in ("VSS", "GND", "AVSS", "DVSS", "GNDA", "GNDD", "GNDP")
    )


def _layout_pins(pin_rows) -> tuple[list[dict], float, float, float, float]:
    """Compute pin coordinates and body metrics for a clean DipTrace symbol.

    Every pin is classified first (top supply / bottom supply / side) and then
    placed explicitly:

    * Side pins run along the left and right edges of the body - left side
      top-to-bottom, right side bottom-to-top so the numbering wraps around
      like a real IC. Left pins point right (``"0"``) and right pins point
      left (``"180"``) so the stub reaches the body, the layout captured in
      ``docs/diptrace/captures/probe.elixml``.
    * Small mixed-power symbols additionally get their supply pins centered on
      the top edge (``"270"``, stub runs down into the body) and their ground
      pins on the bottom edge (``"90"``, stub runs up).

    Returns ``(coords, body_half_height, body_half_width, name_text_y,
    value_text_y)`` where ``coords`` has one placement dict per input row in
    the same order, the body metrics describe the rectangle *only* (the Part
    ``Width``/``Height`` attributes and the rectangle shape must agree), and
    the part ``Name``/``Value`` text offsets are pushed outside any top/bottom
    pin labels so no text can overlap a pin.
    """
    rows = list(pin_rows)
    top_rows = [row for row in rows if _is_top_power_pin(row["name"])]
    bottom_rows = [row for row in rows if _is_bottom_power_pin(row["name"])]
    power_count = len(top_rows) + len(bottom_rows)
    use_vertical_power_pins = (
        MIN_VERTICAL_POWER_SYMBOL_PINS <= len(rows) <= MAX_VERTICAL_POWER_SYMBOL_PINS
        and 1 <= power_count <= MAX_VERTICAL_POWER_PINS
    )

    body_half_width = float(MIN_BODY_HALF_WIDTH)
    # Keep symbol edges on DipTrace's common 50-mil drawing grid.
    body_half_width = float(int((body_half_width + 49.0) // 50.0) * 50)
    side_rows = rows
    if use_vertical_power_pins:
        side_rows = [
            row
            for row in rows
            if row not in top_rows and row not in bottom_rows
        ]

    left_count = (len(side_rows) + 1) // 2
    right_count = len(side_rows) - left_count
    pins_per_side = max(left_count, right_count)
    body_half_height = max(pins_per_side * PIN_PITCH, MIN_SYMBOL_HEIGHT) / 2.0

    coords: list[dict] = []
    # One X slot per top/bottom pin, centered on the edge; slots are assigned
    # by position (never by dict equality) so duplicate power pins stay apart.
    top_count = len(top_rows)
    bottom_count = len(bottom_rows)
    top_x_positions = [
        -((top_count - 1) * PIN_PITCH) / 2.0 + i * PIN_PITCH
        for i in range(top_count)
    ]
    bottom_x_positions = [
        -((bottom_count - 1) * PIN_PITCH) / 2.0 + i * PIN_PITCH
        for i in range(bottom_count)
    ]

    side_index = 0
    top_slot = 0
    bottom_slot = 0
    for row in rows:
        if use_vertical_power_pins and _is_top_power_pin(row["name"]):
            coords.append(
                {
                    "x": top_x_positions[top_slot],
                    "y": body_half_height + PIN_LENGTH,
                    "orientation": "270",
                    "num_x_shift": "0",
                    "num_y_shift": str(-int(_TOP_BOTTOM_NUM_OUTSET)),
                    "name_x_shift": "0",
                    "name_y_shift": str(int(_TOP_BOTTOM_NAME_OUTSET)),
                    "num_orientation": "0",
                    "name_orientation": "0",
                }
            )
            top_slot += 1
            continue
        if use_vertical_power_pins and _is_bottom_power_pin(row["name"]):
            coords.append(
                {
                    "x": bottom_x_positions[bottom_slot],
                    "y": -(body_half_height + PIN_LENGTH),
                    "orientation": "90",
                    "num_x_shift": "0",
                    "num_y_shift": str(int(_TOP_BOTTOM_NUM_OUTSET)),
                    "name_x_shift": "0",
                    "name_y_shift": str(-int(_TOP_BOTTOM_NAME_OUTSET)),
                    "num_orientation": "0",
                    "name_orientation": "0",
                }
            )
            bottom_slot += 1
            continue

        if side_index < left_count:
            y = body_half_height - (side_index + 0.5) * PIN_PITCH
            coords.append(
                {
                    "x": -(body_half_width + PIN_LENGTH),
                    "y": y,
                    "orientation": "0",
                    "num_x_shift": str(int(_NUM_OUTSET)),
                    "num_y_shift": "-20",
                    "name_x_shift": str(-int(_NAME_OUTSET)),
                    "name_y_shift": "20",
                    "num_orientation": "0",
                    "name_orientation": "0",
                }
            )
        else:
            j = side_index - left_count
            y = -body_half_height + (j + 0.5) * PIN_PITCH
            coords.append(
                {
                    "x": body_half_width + PIN_LENGTH,
                    "y": y,
                    "orientation": "180",
                    "num_x_shift": str(-int(_NUM_OUTSET)),
                    "num_y_shift": "-20",
                    "name_x_shift": str(int(_NAME_OUTSET)),
                    "name_y_shift": "20",
                    "num_orientation": "0",
                    "name_orientation": "0",
                }
            )
        side_index += 1

    # Part Name/Value text must clear the pin stubs and any top/bottom pin
    # name labels (a label sits NAME_OUTSET beyond the tip and is about half a
    # font-5 glyph tall). Without vertical power pins this is the body edge
    # plus the text gap, matching probe.elixml.
    name_text_y = body_half_height + NAME_TEXT_GAP
    if use_vertical_power_pins and top_count:
        name_text_y = (
            body_half_height
            + PIN_LENGTH
            + _TOP_BOTTOM_NAME_OUTSET
            + _FONT5_TEXT_HEIGHT / 2.0
            + NAME_TEXT_GAP
        )
    value_text_y = -(body_half_height + VALUE_TEXT_GAP)
    if use_vertical_power_pins and bottom_count:
        value_text_y = -(
            body_half_height
            + PIN_LENGTH
            + _TOP_BOTTOM_NAME_OUTSET
            + _FONT5_TEXT_HEIGHT / 2.0
            + VALUE_TEXT_GAP
        )
    return coords, body_half_height, body_half_width, name_text_y, value_text_y


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

    coords, body_half_height, body_half_width, name_text_y, value_text_y = _layout_pins(
        rows
    )
    width = 2.0 * body_half_width
    height = 2.0 * body_half_height
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
    for index, (placement, row) in enumerate(zip(coords, rows)):
        x = placement["x"]
        y = placement["y"]
        orientation = placement["orientation"]
        electric = pin_electric_type(row["name"])
        lines.append(
            f'          <Pin Id="{index}" X="{_fmt(x)}" Y="{_fmt(y)}" Locked="N" '
            f'Type="Default" ElectricType="{electric}" Orientation="{orientation}" '
            f'PadId="{index}" Length="{_fmt(PIN_LENGTH)}" ShowName="Y" '
            f'NumXShift="{placement["num_x_shift"]}" NumYShift="{placement["num_y_shift"]}" '
            f'NameXShift="{placement["name_x_shift"]}" NameYShift="{placement["name_y_shift"]}" '
            f'SignalDelay="0" NumOrientation="{placement["num_orientation"]}" '
            f'NameOrientation="{placement["name_orientation"]}" Group="-1">'
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
    lines.append(
        f'              <Point X="{_fmt(-body_half_width)}" Y="{_fmt(body_half_height)}"/>'
    )
    lines.append(
        f'              <Point X="{_fmt(body_half_width)}" Y="{_fmt(-body_half_height)}"/>'
    )
    lines.append("            </Points>")
    lines.append("          </Shape>")

    for shape_id, text_show, text_y in (
        (1, "Name", name_text_y),
        (2, "Value", value_text_y),
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
