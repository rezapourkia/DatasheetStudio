"""PyMuPDF-backed PDF reader.

All PyMuPDF usage is isolated inside this module so the rest of the
application only works with the domain models in ``models.pdf_document``.
"""

import os
import re
from pathlib import Path

import pymupdf

from datasheet_studio.models.pdf_document import Bookmark, PdfDocumentInfo, PdfNote


class PdfOpenError(Exception):
    """Raised when a PDF cannot be opened or read."""


class PdfReader:
    """Read PDF files and return domain-level document information."""

    # Matches ST-style pin names at the start of a cell: port pins (PA0..PH1),
    # power pins (VDD, VSS, VDDA, VSSA, VREF, VBAT), NRST, BOOT0, OSC...
    _PIN_NAME_RE = re.compile(r"^(P[ABCDEFGH]\d{1,2}|V[A-Z]{2,6}|NRST|BOOT\d*)")

    # Ball-grid packages (WLCSP, UFBGA...) use alphanumeric ball IDs (A1, B7).
    _BALL_ID_RE = re.compile(r"^[A-Ha-h]\d{1,2}$")

    # Generic pin numbers for non-ST datasheets: plain integers, ranges
    # ("2-3", "2,3") and alphanumeric ball IDs ("A1", "P3", "D6").
    _PIN_NUMBER_RE = re.compile(
        r"^\s*(\d{1,3}(?:\s*[,\-/]\s*\d{1,3}){0,6}|[A-Za-z]{1,3}\d{1,2})\s*$"
    )

    # Package-family tokens used to name generic pinouts (TI/Maxim/ST...).
    _PACKAGE_RE = re.compile(
        r"\b(VQFN|WQFN|HVQFN|QFN|TSSOP|SSOP|MSOP|SOIC|SOP|SOT|DFN|WSON|X2SON|"
        r"UDFN|TDFN|DSBGA|UFBGA|VFBGA|BGA|LQFP|TQFP|QFP|DIP|WLP|VSON|SON|CSP)\b",
        re.I,
    )

    # PyMuPDF save() options per compression level (see save_selected_pages).
    _COMPRESSION_OPTIONS: dict[str, dict] = {
        "fast": {
            "garbage": 1,
            "deflate": True,
            "deflate_images": True,
            "deflate_fonts": True,
        },
        "normal": {
            "garbage": 3,
            "deflate": True,
            "deflate_images": True,
            "deflate_fonts": True,
        },
        "best": {
            "garbage": 4,
            "deflate": True,
            "deflate_images": True,
            "deflate_fonts": True,
            "clean": True,
        },
    }

    def open(self, path: str | Path) -> PdfDocumentInfo:
        """Open a PDF and return its metadata, page count, and bookmarks."""
        # Normalize to an absolute path so later operations (e.g. exporting
        # selected pages) never depend on the process's current directory.
        file_path = Path(os.path.abspath(str(path)))

        if not file_path.is_file():
            raise PdfOpenError(f"File not found: {file_path}")

        try:
            doc = pymupdf.open(str(file_path))
        except Exception as exc:  # noqa: BLE001 - normalize all PyMuPDF errors
            raise PdfOpenError(f"Could not open PDF: {file_path}") from exc

        try:
            if not doc.is_pdf:
                raise PdfOpenError(f"Not a PDF file: {file_path}")

            metadata = doc.metadata or {}
            bookmarks = self._extract_bookmarks(doc)

            return PdfDocumentInfo(
                path=str(file_path),
                page_count=doc.page_count,
                title=metadata.get("title") or "",
                author=metadata.get("author") or "",
                bookmarks=bookmarks,
            )
        finally:
            doc.close()

    def get_page_dimensions(self, path: str | Path, page_number: int) -> tuple[float, float]:
        """Return (width, height) of a 1-based page in PDF points (72 dpi)."""
        file_path = Path(path)
        try:
            doc = pymupdf.open(str(file_path))
        except Exception as exc:
            raise PdfOpenError(f"Could not open PDF: {file_path}") from exc
        try:
            index = int(page_number) - 1
            if index < 0 or index >= doc.page_count:
                raise PdfOpenError(
                    f"Page {page_number} is out of range (1..{doc.page_count})."
                )
            page = doc.load_page(index)
            rect = page.rect
            return (rect.width, rect.height)
        finally:
            doc.close()

    def get_page_text(self, path: str | Path, page_number: int) -> str:
        """Return the extracted text of one 1-based page."""
        file_path = Path(path)
        try:
            doc = pymupdf.open(str(file_path))
        except Exception as exc:  # noqa: BLE001
            raise PdfOpenError(f"Could not open PDF: {file_path}") from exc
        try:
            index = int(page_number) - 1
            if index < 0 or index >= doc.page_count:
                raise PdfOpenError(
                    f"Page {page_number} is out of range (1..{doc.page_count})."
                )
            page = doc.load_page(index)
            return page.get_text().strip()
        finally:
            doc.close()

    def render_page_png(self, path: str | Path, page_number: int, zoom: float = 1.0) -> bytes:
        """Render one 1-based page as PNG bytes.

        The UI consumes these bytes as a standard image, so PyMuPDF stays
        isolated inside this infrastructure module.
        """
        file_path = Path(path)
        zoom = max(0.1, min(float(zoom), 5.0))

        try:
            doc = pymupdf.open(str(file_path))
        except Exception as exc:  # noqa: BLE001
            raise PdfOpenError(f"Could not open PDF: {file_path}") from exc

        try:
            index = int(page_number) - 1
            if index < 0 or index >= doc.page_count:
                raise PdfOpenError(
                    f"Page {page_number} is out of range (1..{doc.page_count})."
                )

            page = doc.load_page(index)
            matrix = pymupdf.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            return pixmap.tobytes("png")
        finally:
            doc.close()

    def add_notes_to_pdf(self, path: str | Path, notes: list[PdfNote]) -> None:
        """Add notes as annotations to the PDF file."""
        file_path = Path(path)
        temp_path = file_path.with_name(file_path.name + ".tmp")

        # Open document with write capability
        doc = pymupdf.open(str(file_path))

        try:
            notes_by_page: dict[int, list[PdfNote]] = {}
            for note in notes:
                notes_by_page.setdefault(note.page_number, []).append(note)

            for page_num, page_notes in notes_by_page.items():
                page_index = page_num - 1
                if 0 <= page_index < doc.page_count:
                    self._annotate_page(doc, page_index, page_notes)

            # Save the modified document to a temporary file
            doc.save(str(temp_path))
        finally:
            doc.close()

        # Replace the original file with the annotated version
        try:
            os.replace(temp_path, file_path)
        except OSError:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def save_selected_pages(
        self,
        source_path: str | Path,
        page_numbers: list[int],
        dest_path: str | Path,
        notes_by_page: dict[int, list[PdfNote]] | None = None,
        compression: str = "none",
    ) -> None:
        """Copy selected pages into a new PDF file.

        When ``notes_by_page`` is provided, the notes for each selected page
        are added to the copied page as text annotations.

        ``compression`` selects the PyMuPDF save options used to shrink the
        output: ``"none"`` (default), ``"fast"``, ``"normal"`` or ``"best"``.
        """
        notes_by_page = notes_by_page or {}
        save_options = self._COMPRESSION_OPTIONS.get(
            (compression or "none").lower(), {}
        )

        try:
            source_doc = pymupdf.open(str(source_path))
        except Exception as exc:  # noqa: BLE001
            raise PdfOpenError(f"Could not open PDF: {source_path}") from exc

        try:
            new_doc = pymupdf.open()
            try:
                for page_num in sorted(page_numbers):
                    page_index = page_num - 1
                    if page_index < 0 or page_index >= source_doc.page_count:
                        raise PdfOpenError(
                            f"Page {page_num} is out of range (1..{source_doc.page_count})."
                        )
                    new_doc.insert_pdf(
                        source_doc, from_page=page_index, to_page=page_index
                    )
                    self._annotate_page(
                        new_doc,
                        new_doc.page_count - 1,
                        notes_by_page.get(page_num, []),
                    )
                new_doc.save(str(dest_path), **save_options)
            finally:
                new_doc.close()
        finally:
            source_doc.close()

        # Ensure the output file was actually written (surface silent failures).
        if not os.path.isfile(dest_path) or os.path.getsize(dest_path) == 0:
            raise PdfOpenError(f"Output file was not created: {dest_path}")

    # ------------------------------------------------------------------
    # Pinout / alternate-function table extraction
    # ------------------------------------------------------------------

    def get_all_pinouts(self, path: str | Path) -> dict[str, list[dict]]:
        """Extract the pinout tables for every package of the datasheet.

        Returns a dict mapping a package name (e.g. ``"LQFP48"``) to a list of
        row dicts with keys ``pin``, ``name``, ``type``, ``alternate_functions``
        and ``additional_functions``. The alternate functions include their AF
        number (e.g. ``AF4=I2C2_SMBA``) when the datasheet's alternate-function
        table is available.

        The pin-definition section is scanned once for all packages, so listing
        packages and extracting several pinouts is fast.
        """
        file_path = Path(path)
        try:
            doc = pymupdf.open(str(file_path))
        except Exception as exc:  # noqa: BLE001
            raise PdfOpenError(f"Could not open PDF: {file_path}") from exc

        try:
            # Both scans run `find_tables` over overlapping page ranges, so
            # share a per-page table cache to avoid extracting them twice.
            tables_cache: dict[int, list] = {}

            def tables_loader(page_no: int) -> list:
                if page_no not in tables_cache:
                    tables_cache[page_no] = (
                        doc.load_page(page_no - 1).find_tables().tables
                    )
                return tables_cache[page_no]

            raw = self._extract_all_pinouts(doc, tables_loader)
            if not raw:
                # Non-ST datasheets (TI, Maxim, ...) often have no TOC and no
                # package-column pin table; fall back to the generic detector.
                raw = self._extract_pinout_generic(doc, tables_loader)
            if not raw:
                return {}

            af_map = self._extract_alternate_function_map(doc, tables_loader)
            af_by_base = {
                self._base_pin_name(name): mapping
                for name, mapping in af_map.items()
            }

            result: dict[str, list[dict]] = {}
            for package, rows in raw.items():
                joined: list[dict] = []
                for row in rows:
                    mapping = af_by_base.get(self._base_pin_name(row["name"]))
                    if mapping:
                        af_text = ", ".join(
                            f"{label}={value}"
                            for label, value in sorted(
                                mapping.items(), key=lambda kv: self._af_sort_key(kv[0])
                            )
                        )
                    else:
                        af_text = row["alternate_functions"]
                    joined.append(
                        {
                            "pin": row["pin"],
                            "name": row["name"],
                            "type": row["type"],
                            "alternate_functions": af_text,
                            "additional_functions": row["additional_functions"],
                        }
                    )
                result[package] = joined
            return result
        finally:
            doc.close()

    @staticmethod
    def package_pin_count(package: str, rows: list[dict]) -> int:
        """Best-effort pin count for a package.

        Prefer the number encoded in the package name (ST names always carry
        it: SO8N=8, TSSOP20=20, LQFP48=48, WLCSP49=49...). This is more
        reliable than counting extracted rows because some datasheet tables
        (e.g. the STM32G030 pin table) visually merge the SO8N/TSSOP20
        columns, which PyMuPDF's table detection cannot always split. Falls
        back to the number of distinct extracted pin numbers.
        """
        match = re.search(r"(\d+)", package or "")
        if match:
            return int(match.group(1))
        return len({r["pin"] for r in rows})

    def get_available_packages(self, path: str | Path) -> list[dict]:
        """List the packages (schematic symbol variants) found in the datasheet.

        Returns ``[{"package": "LQFP48", "pin_count": 48}, ...]`` sorted by pin
        count. One IC frequently has several symbol variants with different pin
        counts (e.g. SO8N, TSSOP20, LQFP32, LQFP48).
        """
        all_pinouts = self.get_all_pinouts(path)
        items = [
            {
                "package": package,
                "pin_count": self.package_pin_count(package, rows),
            }
            for package, rows in all_pinouts.items()
            if rows
        ]
        items.sort(key=lambda item: (item["pin_count"], item["package"]))
        return items

    @staticmethod
    def _norm_pkg(package: str) -> str:
        """Normalize a package name for dict lookups (``lqfp-48`` -> ``LQFP48``)."""
        return re.sub(r"[\s_-]+", "", (package or "").upper())

    def get_pinout(self, path: str | Path, package: str = "LQFP48") -> list[dict]:
        """Extract the pinout table for one package of the datasheet.

        See :meth:`get_all_pinouts` for the row structure.
        """
        norm = self._norm_pkg(package)
        for key, rows in self.get_all_pinouts(path).items():
            if self._norm_pkg(key) == norm:
                return rows
        return []

    def _find_section_page(self, doc, keywords: list[str]) -> int | None:
        """Return the 1-based page of the first TOC section matching any keyword."""
        try:
            toc = doc.get_toc()
        except Exception:  # noqa: BLE001 - unsupported TOC should be safe
            return None
        for _level, title, page in toc:
            title_lower = str(title).lower()
            if any(k in title_lower for k in keywords):
                return max(1, int(page))
        return None

    def _section_page_range(
        self,
        doc,
        primary_keywords: list[str],
        fallback_keywords: list[str] | None = None,
    ) -> tuple[int, int]:
        """Return ``(start, end)`` 1-based page bounds of the TOC section
        matching one of ``primary_keywords`` (or ``fallback_keywords``).

        The end is bounded by the next top-level section so table scans stay
        fast (``page.find_tables`` is expensive). If no TOC entry matches, the
        first 60 pages are scanned as a fallback.
        """
        start = self._find_section_page(doc, primary_keywords)
        if start is None and fallback_keywords:
            start = self._find_section_page(doc, fallback_keywords)
        try:
            toc = doc.get_toc()
        except Exception:  # noqa: BLE001 - unsupported TOC should be safe
            toc = []
        if start is None:
            return 1, min(doc.page_count, 60)
        top_level_pages = [
            max(1, int(page)) for level, _title, page in toc if level == 1
        ]
        end = None
        for p in top_level_pages:
            if p > start:
                end = p - 1
                break
        if end is None:
            end = min(doc.page_count, start + 25)
        return start, end

    @staticmethod
    def _clean_cell(cell) -> str:
        """Clean a table cell, dropping PyMuPDF '_'/newline cell artifacts."""
        if cell is None:
            return ""
        text = re.sub(r"[_\n]+", " ", str(cell))
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _base_pin_name(pin_name: str) -> str:
        """Reduce a pin name to its base for cross-table matching.

        ``"PC14-OSC32_IN"`` -> ``"PC14"``, ``"PB8-BOOT0"`` -> ``"PB8"``.
        """
        base = (pin_name or "").split("-")[0].split("/")[0].strip()
        return re.sub(r"[\s_]+", "", base).upper()

    @staticmethod
    def _pin_sort_key(value: str) -> tuple[int, int | str]:
        """Sort pin values numerically first, then keep non-numeric stable."""
        token = str(value).strip()
        match = re.match(r"^\s*(\d{1,4})", token)
        if match:
            return (0, int(match.group(1)))
        return (1, token.upper())

    @staticmethod
    def _af_sort_key(label: str) -> int:
        """Sort key for AF labels so AF10 sorts after AF9."""
        match = re.search(r"(\d+)", label or "")
        return int(match.group(1)) if match else 0

    def _extract_all_pinouts(
        self, doc, tables_loader=None
    ) -> dict[str, list[dict]]:
        """Scan the pin-definition section once and return rows for every package.

        The header page provides the package columns and the name/type/AF
        column positions; those positions are reused on the continuation pages
        so the multi-page table is merged correctly. Rows are validated
        (numeric pin number + pin-name pattern) so unrelated tables on nearby
        pages are never picked up. Returns ``{normalized_package: [rows]}``.
        ``tables_loader`` (optional) is a callable ``page_no -> tables`` used to
        share a ``find_tables`` cache with the alternate-function scan.
        """
        start, end = self._section_page_range(
            doc,
            ["pin definition", "pin assignment"],
            ["pin description", "pinouts and pin", "pinouts, pin"],
        )
        no_toc_section = (
            self._find_section_page(doc, ["pin definition", "pin assignment"]) is None
            and self._find_section_page(
                doc, ["pin description", "pinouts and pin", "pinouts, pin"]
            )
            is None
        )
        pkg_cols: dict[str, int] = {}  # normalized package -> column index
        col_indices: tuple | None = None  # (name, type, af, additional)
        rows: dict[str, list[dict]] = {}
        seen_table = False
        empty_streak = 0

        def _tables(pno: int):
            if tables_loader is not None:
                return tables_loader(pno)
            return doc.load_page(pno - 1).find_tables().tables

        def _cell(index, row, indices):
            i = indices[index]
            if i is None or i >= len(row):
                return ""
            return PdfReader._clean_cell(row[i])

        for pno in range(start, end + 1):
            rows_before = sum(len(v) for v in rows.values())

            for table in _tables(pno):
                data = table.extract()
                if not data or len(data[0]) < 3:
                    continue

                if col_indices is None:
                    header = [str(c or "") for c in data[0]]
                    if not any("pin name" in h.lower() for h in header):
                        continue
                    sub = [str(c or "") for c in (data[1] if len(data) > 1 else [])]
                    for i, raw in enumerate(sub):
                        norm = self._norm_pkg(raw)
                        if norm and norm not in pkg_cols:
                            pkg_cols[norm] = i
                            rows[norm] = []
                    if not pkg_cols:
                        continue
                    name_col = next(
                        (i for i, h in enumerate(header) if "pin name" in h.lower()), None
                    )
                    type_col = next(
                        (i for i, h in enumerate(header) if "pin type" in h.lower()), None
                    )
                    af_col = next(
                        (
                            i
                            for i, h in enumerate(header)
                            if "alternate" in h.lower()
                        ),
                        None,
                    )
                    addl_col = next(
                        (
                            i
                            for i, h in enumerate(header)
                            if "additional" in h.lower()
                        ),
                        None,
                    )
                    col_indices = (name_col, type_col, af_col, addl_col)
                    seen_table = True
                    data_rows = data[2:]  # skip the two header rows
                else:
                    if table.col_count < max(pkg_cols.values()) + 1:
                        continue
                    data_rows = data

                for row in data_rows:
                    name = _cell(0, row, col_indices)
                    if not self._PIN_NAME_RE.match(name):
                        continue
                    for norm, pcol in pkg_cols.items():
                        if pcol >= len(row):
                            continue
                        pin_val = str(row[pcol] or "").strip()
                        if not pin_val:
                            continue
                        if not (pin_val.isdigit() or self._BALL_ID_RE.match(pin_val)):
                            continue
                        if pin_val.isdigit() and int(pin_val) < 1:
                            continue
                        rows[norm].append(
                            {
                                "pin": pin_val,
                                "name": name,
                                "type": _cell(1, row, col_indices),
                                "alternate_functions": _cell(2, row, col_indices),
                                "additional_functions": _cell(3, row, col_indices),
                            }
                        )

            if sum(len(v) for v in rows.values()) > rows_before:
                empty_streak = 0
            elif seen_table:
                empty_streak += 1
                if empty_streak >= 5:
                    break
            elif no_toc_section and pno - start >= 10:
                # No TOC section and no ST-style table in the first pages:
                # give up quickly so the generic detector can run.
                break

        for norm in list(rows.keys()):
            if not rows[norm]:
                del rows[norm]
            else:
                # Numeric pin numbers sort numerically; ball IDs keep the
                # datasheet's row order (stable sort with a constant key).
                rows[norm].sort(key=lambda r: self._pin_sort_key(r["pin"]))
        return rows

    def _extract_alternate_function_map(
        self, doc, tables_loader=None
    ) -> dict[str, dict[str, str]]:
        """Extract the AF0..AF15 alternate-function table.

        Returns a dict mapping a base pin name (e.g. ``PA0``) to a dict of
        ``AF`` labels -> function text (e.g. ``{"AF1": "TIM2 CH1", ...}``).
        ``tables_loader`` (optional) shares a ``find_tables`` cache with the
        pin-definition scan.
        """
        start, end = self._section_page_range(
            doc, ["alternate function"], ["alternate functions"]
        )
        af_map: dict[str, dict[str, str]] = {}
        seen_table = False
        empty_streak = 0

        for pno in range(start, end + 1):
            page_matched = False

            for table in (
                tables_loader(pno)
                if tables_loader is not None
                else doc.load_page(pno - 1).find_tables().tables
            ):
                data = table.extract()
                if not data or len(data[0]) < 3:
                    continue
                header = [str(c or "") for c in data[0]]
                af_cols = [
                    i
                    for i, c in enumerate(header)
                    if str(c or "").strip().startswith("AF")
                ]
                if len(af_cols) < 2:
                    continue
                if not any(str(c or "").strip() == "AF0" for c in header):
                    continue

                seen_table = True
                page_matched = True
                for row in data[2:]:
                    if len(row) < 2:
                        continue
                    raw_name = str(row[1] or "").strip()
                    if not raw_name or raw_name.lower().startswith("port"):
                        continue
                    base = self._base_pin_name(raw_name)
                    if not base:
                        continue
                    mapping: dict[str, str] = {}
                    for i in af_cols:
                        if i >= len(row):
                            break
                        value = self._clean_cell(row[i])
                        if value and value != "-":
                            mapping[str(header[i]).strip()] = value
                    if mapping:
                        af_map[base] = mapping

            if page_matched:
                empty_streak = 0
            elif seen_table:
                empty_streak += 1
                if empty_streak >= 5:
                    break
            elif pno >= start + 80:
                break

        return af_map

    # ------------------------------------------------------------------
    # Generic pin-table extraction (non-ST datasheets)
    # ------------------------------------------------------------------

    @staticmethod
    def _pin_table_columns(data) -> tuple[int, int, int | None, int | None] | None:
        """Detect pin-table columns from a (possibly two-row) header.

        Returns ``(name_col, num_col, type_col, desc_col)`` (type/desc may be
        ``None``) when the header looks like a pin table, else ``None``.
        Handles merged two-row headers such as ``PIN`` spanning ``NAME``/``NO.``.
        """
        if not data or not data[0]:
            return None
        r0 = [str(c or "").strip().lower() for c in data[0]]
        r1 = [str(c or "").strip().lower() for c in (data[1] if len(data) > 1 else [])]
        ncols = max(len(r0), len(r1))

        def combined(i: int) -> str:
            a = r0[i] if i < len(r0) else ""
            b = r1[i] if i < len(r1) else ""
            return " ".join(x for x in (a, b) if x)

        name_col = num_col = type_col = desc_col = None
        for i in range(ncols):
            text = combined(i)
            if not text:
                continue
            if name_col is None and re.search(
                r"pin\s*name|(^|\s)name($|\s)|signal|terminal", text
            ):
                name_col = i
            elif num_col is None and "name" not in text and re.search(
                r"\bpin\b|\bno\.?\b|number|\bball\b|\bpad\b|#", text
            ):
                num_col = i
            elif type_col is None and re.search(r"\btype\b|i/o|in/out|direction", text):
                type_col = i
            elif desc_col is None and re.search(
                r"descript|function|details|feature", text
            ):
                desc_col = i

        if name_col is None:
            return None
        # Without a number/ball column, only fall back to column 0 when that
        # column's header is explicitly a pin/ball/pad column (not a "name"
        # column) — otherwise ST-style "Pin Name" tables would be misread.
        if num_col is None:
            if name_col == 0 or not re.search(
                r"\bpin\b|\bball\b|\bpad\b|\bno\.?\b|number", combined(0)
            ):
                return None
            num_col = 0
        return name_col, num_col, type_col, desc_col

    @staticmethod
    def _header_row_count(data) -> int:
        """How many leading header rows a pin table uses (1 or 2)."""
        count = 0
        for i in range(min(2, len(data))):
            cells = [
                str(c or "").strip().lower()
                for c in data[i]
                if str(c or "").strip()
            ]
            if not cells:
                break
            if re.search(
                r"pin\s*name|(^|\s)name($|\s)|\bno\.?\b|number|\bball\b|\bpad\b|"
                r"\btype\b|descript|function|\bpin\b",
                " ".join(cells),
            ):
                count += 1
            else:
                break
        return max(count, 1)

    @staticmethod
    def _valid_generic_pin_name(name: str) -> bool:
        """Accept a row as a pin only if its name cell looks like a pin name."""
        if not name:
            return False
        low = name.strip().lower()
        if low in {
            "name", "pin", "description", "type", "no.", "no", "function",
            "signal", "ball", "pad", "num", "number",
        }:
            return False
        if low.startswith("note") or low.startswith("see note"):
            return False
        return bool(re.search(r"[A-Za-z0-9]", name))

    @staticmethod
    def _detect_package(page_text: str, pin_count: int) -> str:
        """Best-effort package name from page text (``VQFN29``, ``TSSOP20``...).

        Only counts near the package-family token are trusted (``VQFN (29)``,
        ``28-Pin TSSOP``), so section headings like ``5 Pin Configuration``
        cannot be misread as a pin count.
        """
        text = page_text or ""
        m = PdfReader._PACKAGE_RE.search(text)
        if not m:
            return f"{pin_count}P"
        family = m.group(1).upper()
        window = text[max(0, m.start() - 40) : min(len(text), m.end() + 40)]
        count = ""
        m2 = re.search(r"\((\d{1,3})\)", window)
        if not m2:
            m2 = re.search(
                r"(\d{1,3})\s*-?\s*(?:pin|pins|lead|leads|package)\b",
                window,
                re.I,
            )
        if not m2:
            m2 = re.search(rf"{re.escape(family)}\s*[- ]?(\d{{1,3}})\b", window)
        if m2:
            count = m2.group(1)
        return f"{family}{count}" if count else family

    def _extract_pinout_generic(
        self, doc, tables_loader=None
    ) -> dict[str, list[dict]]:
        """Generic single-package pin-table extraction (non-ST datasheets).

        Works without a PDF TOC and without ST-style headers: detects a pin
        table by its header keywords (``NAME``/``NO.``/``TYPE``/``DESCRIPTION``,
        ``PIN``/``NAME``/``FUNCTION``, ...), accepts numeric, range and ball pin
        numbers, and merges continuation pages. It also handles tables where
        multiple package columns are present in a single table and share one
        common pin-name column (for example some Microchip datasheets). Package
        names may appear in either the header row or the first data row.
        Returns ``{package: [rows]}``.
        """
        max_scan = min(doc.page_count, 40)
        columns: tuple | None = None
        header_rows = 0
        rows: list[dict] = []
        package = ""
        seen: set[tuple[str, str]] = set()
        packages: dict[str, list[dict]] = {}
        seen_by_package: dict[str, set[tuple[str, str]]] = {}
        empty_streak = 0
        package_columns: list[tuple[int, str]] = []

        def _tables(pno: int):
            if tables_loader is not None:
                return tables_loader(pno)
            return doc.load_page(pno - 1).find_tables().tables

        def _collect_package_columns(header_row: list) -> list[tuple[int, str]]:
            """Collect package columns from a shared header row."""
            found: list[tuple[int, str]] = []
            seen_names: set[str] = set()
            for idx, raw in enumerate(header_row):
                text = self._clean_cell(raw)
                if not text:
                    continue
                if not self._PACKAGE_RE.search(text):
                    continue
                package_name = self._detect_package(text, 0)
                norm = self._norm_pkg(package_name)
                if norm in seen_names:
                    continue
                seen_names.add(norm)
                found.append((idx, package_name))
            return found

        def _append_package_row(
            package_name: str,
            pin: str,
            row: list,
            name: str,
            type_col: int | None,
            desc_col: int | None,
        ) -> None:
            norm = self._norm_pkg(package_name)
            package_rows = packages.setdefault(norm, [])
            seen_pkg = seen_by_package.setdefault(norm, set())
            key = (pin, name)
            if key in seen_pkg:
                return
            seen_pkg.add(key)
            package_rows.append(
                {
                    "pin": pin,
                    "name": name,
                    "type": (
                        self._clean_cell(row[type_col])
                        if type_col is not None and type_col < len(row)
                        else ""
                    ),
                    "alternate_functions": "",
                    "additional_functions": (
                        self._clean_cell(row[desc_col])
                        if desc_col is not None and desc_col < len(row)
                        else ""
                    ),
                }
            )

        for pno in range(1, max_scan + 1):
            rows_before = len(rows) + sum(len(values) for values in packages.values())
            for table in _tables(pno):
                data = table.extract()
                if not data:
                    continue
                cols = columns if columns is not None else self._pin_table_columns(data)
                if cols is None:
                    continue
                name_col, num_col, type_col, desc_col = cols
                if columns is None:
                    columns = cols
                    header_rows = self._header_row_count(data)
                    package_columns = _collect_package_columns(data[0])
                    if not package_columns:
                        first_data_row = header_rows
                        if len(data) > first_data_row:
                            candidate = _collect_package_columns(data[first_data_row])
                            if len(candidate) > 1:
                                package_columns = candidate
                                header_rows += 1
                data_rows = data[header_rows:]

                if package_columns and len(package_columns) > 1:
                    for row in data_rows:
                        name = self._clean_cell(
                            row[name_col] if name_col < len(row) else None
                        )
                        if not self._valid_generic_pin_name(name):
                            continue
                        for pcol, package_name in package_columns:
                            if pcol >= len(row):
                                continue
                            pin = self._clean_cell(row[pcol])
                            if not self._PIN_NUMBER_RE.match(pin):
                                continue
                            _append_package_row(
                                package_name, pin, row, name, type_col, desc_col
                            )
                    continue

                for row in data_rows:
                    name = self._clean_cell(
                        row[name_col] if name_col < len(row) else None
                    )
                    if not self._valid_generic_pin_name(name):
                        continue
                    num = self._clean_cell(row[num_col] if num_col < len(row) else None)
                    if not self._PIN_NUMBER_RE.match(num):
                        continue
                    key = (num, name)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "pin": num,
                            "name": name,
                            "type": (
                                self._clean_cell(row[type_col])
                                if type_col is not None and type_col < len(row)
                                else ""
                            ),
                            "alternate_functions": "",
                            "additional_functions": (
                                self._clean_cell(row[desc_col])
                                if desc_col is not None and desc_col < len(row)
                                else ""
                            ),
                        }
                    )
                if not package and rows:
                    package = self._detect_package(
                        doc.load_page(pno - 1).get_text(), len(rows)
                    )

            rows_seen = len(rows) + sum(len(values) for values in packages.values())
            if rows_seen > rows_before:
                empty_streak = 0
            elif rows_seen:
                empty_streak += 1
                if empty_streak >= 6:
                    break

        if packages:
            for package_rows in packages.values():
                package_rows.sort(key=lambda row: self._pin_sort_key(row["pin"]))
            return packages
        if not rows:
            return {}
        if not package:
            package = f"{len(rows)}P"
        rows.sort(key=lambda row: self._pin_sort_key(row["pin"]))
        return {self._norm_pkg(package): rows}

    def extraction_hint(self, path: str | Path) -> str:
        """Human-readable reason when no pinout was found, else ``""``."""
        file_path = Path(path)
        try:
            doc = pymupdf.open(str(file_path))
        except Exception:  # noqa: BLE001 - unreadable file gets no hint
            return ""
        try:
            if doc.page_count <= 3:
                return (
                    f"This file looks incomplete — it has only {doc.page_count} "
                    "page(s) (probably just the datasheet's first page), so it "
                    "contains no pin table. Download the full datasheet PDF."
                )
            if not self.get_all_pinouts(str(file_path)):
                return "No pin (pinout) table was found in this datasheet."
            return ""
        finally:
            doc.close()

    @staticmethod
    def _annotate_page(doc, page_index: int, notes: list[PdfNote]) -> None:
        """Add sticky-note annotations to one 0-based page of an open document."""
        page = doc.load_page(page_index)
        page_rect = page.rect
        for note in notes:
            x_pos = note.x * page_rect.width
            y_pos = note.y * page_rect.height
            text_annot = page.add_text_annot(pymupdf.Point(x_pos, y_pos), note.text)
            text_annot.set_info(title="Datasheet Studio")
            text_annot.update()

    @staticmethod
    def _extract_bookmarks(doc) -> list[Bookmark]:
        """Extract the flattened outline with 1-based page numbers and levels."""
        try:
            toc = doc.get_toc()
        except Exception:  # noqa: BLE001 - unsupported TOC should be safe
            return []

        bookmarks: list[Bookmark] = []
        for level, title, page in toc:
            bookmarks.append(
                Bookmark(
                    title=title,
                    page=max(1, int(page)),
                    level=max(1, int(level)),
                )
            )
        return bookmarks
