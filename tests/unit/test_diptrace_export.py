"""Tests for the DipTrace component-library (``.elixml``) export service."""

import xml.etree.ElementTree as ET

import pytest

from datasheet_studio.infrastructure.pdf.reader import PdfReader
from datasheet_studio.services.diptrace_export import (
    build_component_library,
    expand_pin_numbers,
    extract_part_number,
    pin_electric_type,
    sanitize_name,
    short_pin_name,
    validate_pin_rows,
)


def test_pin_electric_type_heuristic():
    """Power pins and reset pins get useful ERC types, signals stay Undefined."""
    assert pin_electric_type("VDD") == "Power"
    assert pin_electric_type("VSS") == "Power"
    assert pin_electric_type("VDDA") == "Power"
    assert pin_electric_type("AVSS") == "Power"
    assert pin_electric_type("VBAT") == "Power"
    assert pin_electric_type("VREF+") == "Power"
    assert pin_electric_type("PC13") == "Undefined"
    assert pin_electric_type("NRST") == "Input"
    assert pin_electric_type("") == "Undefined"


def test_sanitize_name():
    """Free-text names become safe filename/library tokens."""
    assert sanitize_name("STM32G431 LQFP48") == "STM32G431_LQFP48"
    assert sanitize_name("a//b__c") == "a_b_c"
    assert sanitize_name("") == "IC"
    assert sanitize_name("   ") == "IC"
    assert sanitize_name("", fallback="pkg") == "pkg"


def test_short_pin_name():
    """Verbose datasheet pin names are shortened for on-symbol display."""
    assert short_pin_name("PC14- OSC32 IN") == "PC14"
    assert short_pin_name("PC15-OSC32 OUT") == "PC15"
    assert short_pin_name("PF0-OSC IN") == "PF0"
    assert short_pin_name("PB8-BOOT0") == "PB8"
    assert short_pin_name("PG10-NRST") == "PG10"
    assert short_pin_name("VBAT") == "VBAT"
    assert short_pin_name("VREF+") == "VREF+"
    assert short_pin_name("OSC_IN") == "OSC_IN"
    assert short_pin_name("") == ""


def test_extract_part_number():
    """Part numbers are found in file names/titles without false positives."""
    assert extract_part_number("STM32G030K8T6-STMicroelectronics") == "STM32G030K8T6"
    assert extract_part_number("STM32G431zzzz-Datasheet") == "STM32G431"
    assert extract_part_number("1324_MAX17201-MAX17215_1-2.pdf") == "MAX17201"
    assert extract_part_number("14684_MAX17320G20-T_1-1") == "MAX17320G20"
    assert extract_part_number("BQ25798 I2 C Controlled Buck-Boost Battery") == "BQ25798"
    # The digit requirement rejects plain English words.
    assert extract_part_number("Maximum efficiency datasheet") == ""
    assert extract_part_number("adapter board schematic") == ""
    assert extract_part_number("Arm Cortex-M0+ 32-bit MCU, timers, ADC") == ""
    # Titles work as a fallback source.
    assert extract_part_number("STM32G431zzzz Datasheet - sisoog") == "STM32G431"
    assert extract_part_number("") == ""
    assert extract_part_number(None) == ""


def test_build_library_lqfp48_real_pinout():
    """A real 48-pin datasheet pinout produces a valid, dense symbol library."""
    reader = PdfReader()
    rows = reader.get_pinout("example/STM32G431zzzz-Datasheet.pdf", "LQFP48")
    assert len(rows) == 48

    xml_text = build_component_library(
        rows, component_name="STM32G431", package="LQFP48"
    )
    root = ET.fromstring(xml_text)

    assert root.attrib["Type"] == "DipTrace-ComponentLibrary"
    assert root.attrib["Name"] == "STM32G431 LQFP48"
    assert root.attrib["Units"] == "mil"
    assert 0 < int(root.attrib["UID32"]) <= 2**31 - 1

    part = root.find(".//Component/Part")
    assert part is not None
    assert part.attrib["RefDes"] == "U"
    assert part.attrib["PartType"] == "Normal"
    assert part.attrib["Type"] == "Free"
    assert part.find("Name").text == "STM32G431"
    assert part.find("Value").text == "STM32G431"

    pins = part.findall("Pins/Pin")
    assert len(pins) == 48
    # Dense, position-bound Ids: every pin's Id equals its list position.
    assert [pin.get("Id") for pin in pins] == [str(i) for i in range(48)]
    assert [pin.get("PadId") for pin in pins] == [str(i) for i in range(48)]
    assert [pin.findtext("PadNumber") for pin in pins] == [
        str(i) for i in range(1, 49)
    ]

    # Two-sided box: first half left (0 -> stub reaches body), second half
    # right (180 -> stub reaches body).
    left = pins[:24]
    right = pins[24:]
    assert all(pin.get("Orientation") == "0" for pin in left)
    assert all(pin.get("Orientation") == "180" for pin in right)
    assert all(abs(float(pin.get("X"))) == 300.0 for pin in pins)
    # Mirrored layout: left top pairs with right top, left bottom with right
    # bottom (same Y rows on both sides).
    assert left[0].get("Y") == right[-1].get("Y")
    assert left[-1].get("Y") == right[0].get("Y")
    # DipTrace-like free pin style: labels are outside the pin row and mirrored.
    assert all(pin.get("NameXShift") == "-55" for pin in left)
    assert all(pin.get("NumXShift") == "40" for pin in left)
    assert all(pin.get("NameXShift") == "55" for pin in right)
    assert all(pin.get("NumXShift") == "-40" for pin in right)

    # Power pins are typed for ERC.
    by_name = {pin.findtext("Name"): pin for pin in pins}
    assert by_name["VDD"].get("ElectricType") == "Power"
    assert by_name["VSS"].get("ElectricType") == "Power"
    assert by_name["PA5"].get("ElectricType") == "Undefined"

    # Graphics: one rectangle body plus Name/Value texts.
    shapes = part.findall("Shapes/Shape")
    assert any(s.get("Type") == "Rectangle" for s in shapes)
    text_shows = {s.get("TextShow") for s in shapes if s.get("Type") == "Text"}
    assert {"Name", "Value"} <= text_shows


def test_build_library_odd_pin_count_and_ball_ids():
    """Odd pin counts split left/right; alphanumeric ball IDs are preserved."""
    rows = [
        {"pin": "A1", "name": "GND"},
        {"pin": "B7", "name": "SCL&<x>"},
        {"pin": "C3", "name": "VDD"},
    ]
    xml_text = build_component_library(
        rows, component_name="SENSOR", package="WLCSP", value="SENSOR-1"
    )
    root = ET.fromstring(xml_text)
    pins = root.findall(".//Pins/Pin")

    assert len(pins) == 3
    assert [p.findtext("PadNumber") for p in pins] == ["A1", "B7", "C3"]
    assert [p.get("Orientation") for p in pins] == ["0", "0", "180"]
    # Special characters are XML-escaped in the stored pin name.
    assert pins[1].findtext("Name") == "SCL&<x>"
    assert "&amp;" in xml_text and "&lt;" in xml_text

    assert root.find(".//Part").find("Value").text == "SENSOR-1"


def test_build_library_places_power_pins_top_and_bottom():
    """Small mixed symbols put supply pins on the top and ground on the bottom."""
    rows = [
        {"pin": "1", "name": "SDA"},
        {"pin": "2", "name": "VDD"},
        {"pin": "3", "name": "GND"},
        {"pin": "4", "name": "SCL"},
    ]
    root = ET.fromstring(build_component_library(rows, component_name="PWR"))
    part = root.find(".//Part")
    assert part is not None
    # Part Width/Height describe the body rectangle only (probe.elixml),
    # never the pin-stub overhang.
    assert part.get("Width") == "400"
    assert part.get("Height") == "300"

    pins = part.findall("Pins/Pin")
    by_name = {pin.findtext("Name"): pin for pin in pins}
    vdd = by_name["VDD"]
    gnd = by_name["GND"]
    assert vdd.get("Orientation") == "270"
    assert vdd.get("X") == "0"
    assert vdd.get("Y") == "250"
    assert gnd.get("Orientation") == "90"
    assert gnd.get("X") == "0"
    assert gnd.get("Y") == "-250"

    # The body rectangle matches the Width/Height attributes.
    rect = next(
        shape
        for shape in part.findall("Shapes/Shape")
        if shape.get("Type") == "Rectangle"
    )
    rect_points = {
        point.get("X"): point.get("Y") for point in rect.findall("Points/Point")
    }
    assert rect_points == {"-200": "150", "200": "-150"}

    # Pin name sits outside the free tip, the number between tip and body, and
    # both stay horizontal — the top/bottom mirror of the probe.elixml side
    # convention. The 65/25 mil split keeps the two labels far apart.
    assert vdd.get("NameYShift") == "65"
    assert vdd.get("NumYShift") == "-25"
    assert vdd.get("NameOrientation") == "0"
    assert vdd.get("NumOrientation") == "0"
    assert gnd.get("NameYShift") == "-65"
    assert gnd.get("NumYShift") == "25"
    assert gnd.get("NameOrientation") == "0"
    assert gnd.get("NumOrientation") == "0"

    # Part Name/Value text is pushed beyond the top/bottom pin name labels so
    # it cannot overlap a power pin or its label.
    text_y = {
        shape.get("TextShow"): float(shape.find("Points/Point").get("Y"))
        for shape in part.findall("Shapes/Shape")
        if shape.get("Type") == "Text"
    }
    assert text_y["Name"] > 250 + 65
    assert text_y["Value"] < -(250 + 65)


def test_build_library_duplicate_ground_pins_do_not_overlap():
    """Two ground pins share the bottom edge at distinct positions."""
    rows = [
        {"pin": "1", "name": "VDD"},
        {"pin": "2", "name": "GND"},
        {"pin": "3", "name": "GND"},
        {"pin": "4", "name": "SDA"},
        {"pin": "5", "name": "SCL"},
    ]
    root = ET.fromstring(build_component_library(rows, component_name="PWR2"))
    pins = root.findall(".//Pins/Pin")

    # Duplicate-named power pins must not collapse onto the same slot.
    grounds = [pin for pin in pins if pin.findtext("Name") == "GND"]
    assert len(grounds) == 2
    assert [g.get("Orientation") for g in grounds] == ["90", "90"]
    assert [g.get("Y") for g in grounds] == ["-250", "-250"]
    assert len({g.get("X") for g in grounds}) == 2

    # No two pins anywhere share a connection point.
    points = [(pin.get("X"), pin.get("Y")) for pin in pins]
    assert len(points) == len(set(points))


def test_pin_row_validation_expands_tied_pad_ranges():
    """A tied-pad range becomes one symbol pin per physical package pad."""
    rows, errors = validate_pin_rows(
        [
            {"pin": "1", "name": "STAT"},
            {"pin": "2-3", "name": "VBUS"},
            {"pin": "4, 5", "name": "GND"},
        ],
        expected_pin_count=5,
    )

    assert errors == []
    assert [row["pin"] for row in rows] == ["1", "2", "3", "4", "5"]
    assert [row["name"] for row in rows] == ["STAT", "VBUS", "VBUS", "GND", "GND"]
    assert [row["pin"] for row in expand_pin_numbers([{"pin": "8-9", "name": "P"}])] == [
        "8",
        "9",
    ]


def test_symbol_body_grows_for_long_labels():
    """Long names stay readable with standard compact two-side body width."""
    rows = [
        {"pin": "1", "name": "LEFT_SIGNAL_LONG"},
        {"pin": "2", "name": "LEFT_OTHER_LONG"},
        {"pin": "3", "name": "RIGHT_SIGNAL_LONG"},
        {"pin": "4", "name": "RIGHT_OTHER_LONG"},
    ]
    root = ET.fromstring(build_component_library(rows, component_name="WIDE"))
    part = root.find(".//Part")
    assert part is not None
    assert float(part.get("Width")) == 400.0
    pins = part.findall("Pins/Pin")
    assert float(pins[0].get("X")) <= -300.0
    assert float(pins[-1].get("X")) >= 300.0


def test_pin_row_validation_rejects_duplicate_or_incomplete_tables():
    """A symbol export must stop for ambiguous duplicate or missing pins."""
    _rows, duplicate_errors = validate_pin_rows(
        [{"pin": "1", "name": "A"}, {"pin": "1", "name": "B"}],
        expected_pin_count=2,
    )
    assert "Duplicate physical pin: 1" in duplicate_errors
    assert any("expects 2 physical pins" in error for error in duplicate_errors)

    _rows, empty_name_errors = validate_pin_rows([{"pin": "1", "name": ""}])
    assert empty_name_errors == ["Pin 1 has no name"]

    with pytest.raises(ValueError, match="needs review"):
        build_component_library(
            [{"pin": "1", "name": "A"}, {"pin": "1", "name": "B"}],
            component_name="BAD",
            expected_pin_count=2,
        )


def test_build_library_requires_rows_and_name():
    """Empty pin lists and missing component names are rejected."""
    with pytest.raises(ValueError):
        build_component_library([], component_name="X")
    with pytest.raises(ValueError):
        build_component_library([{"pin": "1", "name": "A"}], component_name="")
