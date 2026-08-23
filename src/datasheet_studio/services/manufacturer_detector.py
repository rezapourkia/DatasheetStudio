"""Heuristic detection of an IC/vendor name from datasheet cues.

The detector works in order of confidence:
1. PDF metadata ``author`` (e.g. "STMicroelectronics")
2. Filename tokens (e.g. "STM32G431...pdf" -> STMicroelectronics)
3. First-page text (copyright lines, vendor names)

Every step is pure string logic so the module is easy to unit test
without opening PDFs.
"""

import re

# Canonical vendor names keyed by lowercase tokens that commonly appear
# in datasheet filenames. Longer/more specific tokens are matched first.
VENDOR_TOKENS: dict[str, str] = {
    # STMicroelectronics
    "stm": "STMicroelectronics",
    "stm32": "STMicroelectronics",
    "stm8": "STMicroelectronics",
    "stmicro": "STMicroelectronics",
    "stmicroelectronics": "STMicroelectronics",
    "st": "STMicroelectronics",
    # Texas Instruments
    "texasinstruments": "Texas Instruments",
    "texas": "Texas Instruments",
    "ti": "Texas Instruments",
    "tps": "Texas Instruments",
    "sn": "Texas Instruments",
    "lm": "Texas Instruments",
    "ucc": "Texas Instruments",
    "bq": "Texas Instruments",
    # Analog Devices / Maxim
    "analogdevices": "Analog Devices",
    "analog": "Analog Devices",
    "adi": "Analog Devices",
    "maxim": "Analog Devices (Maxim)",
    "max": "Analog Devices (Maxim)",
    "ltc": "Analog Devices",
    "lt": "Analog Devices",
    "ad": "Analog Devices",
    # Microchip
    "microchip": "Microchip",
    "atmega": "Microchip",
    "attiny": "Microchip",
    "atmel": "Microchip",
    "pic": "Microchip",
    "ds": "Microchip",
    "mcp": "Microchip",
    # NXP / Freescale
    "nxp": "NXP",
    "freescale": "NXP",
    # Infineon / Cypress
    "infineon": "Infineon",
    "tle": "Infineon",
    "auir": "Infineon",
    "cypress": "Infineon",
    "psoc": "Infineon",
    # Renesas
    "renesas": "Renesas",
    # onsemi
    "onsemi": "onsemi",
    "on semiconductor": "onsemi",
    # Other common vendors
    "rohm": "ROHM",
    "diodes": "Diodes Incorporated",
    "samsung": "Samsung",
    "broadcom": "Broadcom",
    "intel": "Intel",
    "toshiba": "Toshiba",
    "panasonic": "Panasonic",
    "murata": "Murata",
    "tdk": "TDK",
    "vishay": "Vishay",
    "siliconlabs": "Silicon Labs",
    "espressif": "Espressif",
    "esp32": "Espressif",
    "esp8266": "Espressif",
    "nordic": "Nordic Semiconductor",
    "nrf": "Nordic Semiconductor",
    "marvell": "Marvell",
    "fujitsu": "Fujitsu",
    "epson": "Epson",
    "amphenol": "Amphenol",
    "wurth": "Würth Elektronik",
}

# Ordered longest-first so "texasinstruments" wins over "ti" and "stm32"
# over "st". These tokens are matched anywhere inside the filename.
_SORTED_TOKENS: list[tuple[str, str]] = sorted(
    VENDOR_TOKENS.items(), key=lambda pair: len(pair[0]), reverse=True
)

# Metadata author values that can be trusted as-is (normalized).
_AUTHOR_ALIASES: dict[str, str] = {
    "stmicroelectronics": "STMicroelectronics",
    "texas instruments": "Texas Instruments",
    "analog devices": "Analog Devices",
    "maxim integrated": "Analog Devices (Maxim)",
    "maxim": "Analog Devices (Maxim)",
    "microchip technology": "Microchip",
    "onsemi": "onsemi",
    "on semiconductor": "onsemi",
}


class ManufacturerDetector:
    """Detect a canonical manufacturer name from datasheet clues."""

    @staticmethod
    def from_filename(filename: str) -> str:
        """Return a canonical vendor name found in ``filename``, else ``""``.

        Short tokens (e.g. ``st``, ``ti``) are matched only at a word
        boundary so a file named ``custom-part.pdf`` is not attributed to
        STMicroelectronics via the ``st`` inside ``custom``.
        """
        text = (filename or "").lower()
        if not text:
            return ""
        for token, name in _SORTED_TOKENS:
            pattern = rf"(?:^|[^a-z0-9]){re.escape(token)}"
            if re.search(pattern, text):
                return name
        return ""

    @staticmethod
    def from_metadata(author: str) -> str:
        """Return a canonical vendor name from the PDF ``author`` field."""
        text = (author or "").strip().lower()
        if not text:
            return ""
        if text in _AUTHOR_ALIASES:
            return _AUTHOR_ALIASES[text]
        # "Texas Instruments Incorporated" / "STMicroelectronics SAS" style.
        for key, name in _AUTHOR_ALIASES.items():
            if text.startswith(key) or key in text:
                return name
        for token, name in _SORTED_TOKENS:
            if len(token) >= 4 and token in text:
                return name
        return ""

    @staticmethod
    def from_text(text: str) -> str:
        """Return a canonical vendor name found in page text, else ``""``."""
        sample = (text or "")[:8000].lower()
        if not sample:
            return ""
        for token, name in _SORTED_TOKENS:
            if len(token) >= 4 and token in sample:
                return name
        return ""

    def detect(
        self,
        filename: str,
        author: str = "",
        first_page_text: str = "",
    ) -> str:
        """Best-effort detection; returns a canonical name or ``""``."""
        result = self.from_metadata(author)
        if result:
            return result
        result = self.from_filename(filename)
        if result:
            return result
        return self.from_text(first_page_text)


# Regex for the part-number family prefixes reused by the library index.
PART_FAMILY_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9+])"
    r"((?:STM32|STM8|ATSAM|ATMEGA|ATTINY|AT89|MAX|BQ|AD|LT|LTC|LP|TPS|TUSB|"
    r"LM|DRV|INA|FDC|UCC|IRF|PCA|MCP|MSP430|CC25|CC26|ESP32|ESP8266|nRF52|"
    r"TLE|AUIR|MC9S|MK[0-9])[A-Z0-9+]{2,20})(?![A-Za-z0-9+])"
)


def extract_part_number_from_text(text: str) -> str:
    """Return a plausible component part number found in ``text``, else ``""``."""
    match = PART_FAMILY_RE.search(text or "")
    if not match:
        return ""
    token = match.group(1).upper()
    if not re.search(r"\d", token):
        return ""
    token = re.sub(r"[ZX]{2,}$", "", token)
    return token or ""

