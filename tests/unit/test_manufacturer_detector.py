"""Unit tests for the manufacturer detection heuristics."""

from datasheet_studio.services.manufacturer_detector import (
    ManufacturerDetector,
    extract_part_number_from_text,
)


def test_detect_from_metadata():
    det = ManufacturerDetector()
    assert det.detect("unknown.pdf", author="STMicroelectronics") == "STMicroelectronics"
    assert det.detect("unknown.pdf", author="Texas Instruments Incorporated") == "Texas Instruments"
    assert det.detect("unknown.pdf", author="Maxim Integrated") == "Analog Devices (Maxim)"
    assert det.detect("unknown.pdf", author="Microchip Technology Inc") == "Microchip"


def test_detect_from_filename():
    det = ManufacturerDetector()
    assert det.detect("STM32G431zzzz-Datasheet.pdf") == "STMicroelectronics"
    assert det.detect("TPS54331.pdf") == "Texas Instruments"
    assert det.detect("MAX17201-MAX17215.pdf") == "Analog Devices (Maxim)"
    assert det.detect("ATMEGA328P.pdf") == "Microchip"
    assert det.detect("ATtiny1614.pdf") == "Microchip"
    assert det.detect("BQ25798_1-128.pdf") == "Texas Instruments"
    assert det.detect("ESP32-WROOM.pdf") == "Espressif"
    assert det.detect("nRF52840.pdf") == "Nordic Semiconductor"


def test_detect_longest_token_wins():
    det = ManufacturerDetector()
    # "stm" must not be matched as plain "st".
    assert det.from_filename("STM32F407.pdf") == "STMicroelectronics"
    # "texas" should win over generic "ti".
    assert det.from_filename("Texas-Instruments-TPS54531.pdf") == "Texas Instruments"


def test_detect_from_text():
    det = ManufacturerDetector()
    text = "Copyright (c) 2026 Infineon Technologies AG. All rights reserved."
    assert det.from_text(text) == "Infineon"


def test_detect_returns_empty_for_unknown():
    det = ManufacturerDetector()
    assert det.detect("my-custom-part.pdf") == ""


def test_extract_part_number():
    assert extract_part_number_from_text("STM32G431zzzz") == "STM32G431"
    assert extract_part_number_from_text("TPS54331") == "TPS54331"
    assert extract_part_number_from_text("ATMEGA328P-AU") == "ATMEGA328P"
    assert extract_part_number_from_text("") == ""
    assert extract_part_number_from_text("Datasheet only") == ""
