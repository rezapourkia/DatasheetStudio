"""AI controller-profile extraction with validation and archived runs (Phase 9).

The prompt is a versioned Markdown file; responses are validated against the
Phase 8 field registry before anything reaches a profile. Every run is
archived under the vault at ``ai-runs/<run-id>/`` (request, response,
metadata incl. provider/model, validation result, source hash). Fields enter
a reusable profile ONLY through explicit per-field acceptance in the review
UI — ``accepted_profile`` is the single builder for that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Callable
from uuid import uuid4

from datasheet_studio.models.controller_profile import (
    FIELD_SPECS,
    ControllerProfile,
    ControllerProfileError,
)
from datasheet_studio.models.knowledge_base import EvidenceField, Provenance

PROMPT_VERSION = "controller_extraction_v1"
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / f"{PROMPT_VERSION}.md"

ChatCallable = Callable[[str], str]  # prompt -> response text
CancelCheck = Callable[[], bool]


class ExtractionRunError(RuntimeError):
    """The AI run failed at transport level (provider error, cancel)."""


@dataclass
class ExtractionIssue:
    code: str  # invalid-json | truncation | bad-field | bad-citation | bad-unit
    message: str
    field_name: str = ""


@dataclass
class ExtractionResult:
    raw_response: str = ""
    issues: list[ExtractionIssue] = field(default_factory=list)
    candidate_fields: list[dict] = field(default_factory=list)
    manufacturer: str = ""
    part_number: str = ""
    package: str = ""
    contradictions: list[str] = field(default_factory=list)
    unknown_facts: list[str] = field(default_factory=list)
    run_id: str = ""

    @property
    def ok(self) -> bool:
        return not any(i.code in ("invalid-json", "truncation") for i in self.issues)


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def chunk_plan(
    page_texts: dict[int, str], chunk_pages: int = 10
) -> list[tuple[int, list[int]]]:
    """Deterministically split ALL pages into ordered chunks (no caps)."""

    pages = sorted(page_texts)
    return [
        (index, pages[start : start + chunk_pages])
        for index, start in enumerate(range(0, len(pages), chunk_pages), start=1)
    ]


def build_user_message(
    part_number: str,
    page_texts: dict[int, str],
    chunk_pages: int | None = None,
    chunk_index: int | None = None,
) -> str:
    """User message over the given pages — never truncated (review P1).

    With ``chunk_index`` only that chunk's pages are included; otherwise
    every page. Per-page text is passed in full — no silent caps.
    """

    allowed = "\n".join(
        f"- {spec.name} [{spec.unit or 'enum'}]"
        + (f" (one of: {', '.join(spec.enum_values)})" if spec.enum_values else "")
        for spec in FIELD_SPECS.values()
    )
    if chunk_index is not None:
        plan = dict(chunk_plan(page_texts, chunk_pages or 10))
        pages = plan.get(chunk_index, [])
    else:
        pages = sorted(page_texts)
    context = "\n\n".join(
        f"<!-- page:{number} -->\n{page_texts[number]}" for number in pages
    )
    return (
        f"Extract the controller profile for part «{part_number or 'unknown'}».\n\n"
        f"Allowed fields (name [unit]):\n{allowed}\n\n"
        f"Document text with page markers (extract ONLY from these pages, cite them):\n{context}\n\n"
        "Respond with ONLY the JSON object per the system instructions."
    )


def parse_response(response: str, page_count: int) -> ExtractionResult:
    result = ExtractionResult(raw_response=response)
    text = response.strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        result.issues.append(
            ExtractionIssue(
                "invalid-json" if exc.pos == 0 else "truncation",
                f"پاسخ JSON معتبر نیست: {exc}",
            )
        )
        return result
    if not isinstance(data, dict):
        result.issues.append(ExtractionIssue("invalid-json", "پاسخ یک شیء JSON نیست."))
        return result

    result.manufacturer = str(data.get("manufacturer", "")).strip()
    result.part_number = str(data.get("part_number", "")).strip()
    result.package = str(data.get("package", "")).strip()
    result.contradictions = [str(c) for c in data.get("contradictions", [])]
    result.unknown_facts = [str(u) for u in data.get("unknown_facts", [])]

    for item in data.get("fields", []):
        if not isinstance(item, dict):
            result.issues.append(ExtractionIssue("bad-field", "ساختار فیلد نامعتبر است."))
            continue
        name = str(item.get("name", "")).strip()
        spec = FIELD_SPECS.get(name)
        if spec is None:
            result.issues.append(
                ExtractionIssue("bad-field", f"نام فیلد مجاز نیست: {name}", name)
            )
            continue
        unit = str(item.get("unit", "") or "").strip()
        if spec.unit and unit != spec.unit:
            result.issues.append(
                ExtractionIssue(
                    "bad-unit",
                    f"واحد «{name}» باید «{spec.unit}» باشد؛ پاسخ: «{unit}»",
                    name,
                )
            )
            continue
        page = item.get("page")
        if not isinstance(page, int) or not 1 <= page <= max(1, page_count):
            result.issues.append(
                ExtractionIssue(
                    "bad-citation",
                    f"ارجاع صفحهٔ نامعتبر برای «{name}»: {page!r} (سند {page_count} صفحه دارد)",
                    name,
                )
            )
            continue
        result.candidate_fields.append(item)
    return result


def run_extraction(
    chat: ChatCallable,
    *,
    part_number: str,
    page_texts: dict[int, str],
    page_count: int,
    source_hash: str,
    should_cancel: CancelCheck | None = None,
) -> tuple[ExtractionResult, str, str]:
    """Send the versioned prompt (explicit user action only) and validate.

    Returns (result, request_text, response_text) for archiving.
    """

    if should_cancel and should_cancel():
        raise ExtractionRunError("استخراج پیش از ارسال لغو شد.")
    system = load_prompt()
    user = build_user_message(part_number, page_texts)
    try:
        response = chat(f"{system}\n\n---\n\n{user}")
    except Exception as exc:  # noqa: BLE001 - provider failure
        raise ExtractionRunError(f"ارتباط با ارائه‌دهندهٔ AI ناموفق بود: {exc}") from exc
    result = parse_response(response, page_count)
    result.run_id = uuid4().hex[:12]
    return result, f"{system}\n\n---\n\n{user}", response


@dataclass
class CompleteExtraction:
    """Outcome of a coverage-driven, chunked complete-document run."""

    result: ExtractionResult
    omitted_pages: list[int]
    complete: bool
    chunk_count: int


def extract_complete(
    chat: ChatCallable,
    *,
    part_number: str,
    page_texts: dict[int, str],
    complete_pages,
    page_count: int,
    source_hash: str,
    chunk_pages: int = 10,
    archive_root: Path | None = None,
    provider: str = "",
    model: str = "",
    should_cancel: CancelCheck | None = None,
) -> CompleteExtraction:
    """Chunked multi-pass extraction with a deterministic merge (review P1).

    Driven by the Phase-7 coverage ledger: only ledger-complete pages are
    sent; the rest are reported as ``omitted_pages`` and the run can never
    claim ``complete`` while any page is unaccounted for. Every chunk
    request/response plus the merge artifact are archived under
    ``archive_root/<run-id>/`` when a root is given.
    """

    eligible = {page: page_texts[page] for page in complete_pages if page in page_texts}
    omitted = sorted(set(range(1, page_count + 1)) - set(eligible))
    system = load_prompt()
    merged = ExtractionResult(run_id=uuid4().hex[:12])
    run_id = merged.run_id
    conflicts: dict[str, list] = {}
    chunk_reports: list[dict] = []

    for index, pages in chunk_plan(eligible, chunk_pages):
        if should_cancel and should_cancel():
            raise ExtractionRunError("استخراج پیش از ارسال لغو شد.")
        user = build_user_message(part_number, eligible, chunk_pages, index)
        prompt = f"{system}\n\n---\n\n{user}"
        try:
            response = chat(prompt)
        except Exception as exc:  # noqa: BLE001 - provider failure
            raise ExtractionRunError(
                f"ارتباط با ارائه‌دهندهٔ AI ناموفق بود: {exc}"
            ) from exc
        chunk_result = parse_response(response, page_count)
        chunk_reports.append(
            {
                "chunk": index,
                "pages": pages,
                "ok": chunk_result.ok,
                "issues": [i.__dict__ for i in chunk_result.issues],
            }
        )
        merged.issues.extend(chunk_result.issues)
        if not merged.manufacturer and chunk_result.manufacturer:
            merged.manufacturer = chunk_result.manufacturer
        if not merged.part_number and chunk_result.part_number:
            merged.part_number = chunk_result.part_number
        merged.package = merged.package or chunk_result.package
        merged.unknown_facts.extend(chunk_result.unknown_facts)
        # Round-3 fix: contradictions the MODEL declared must survive the
        # merge (they were silently dropped before).
        merged.contradictions.extend(chunk_result.contradictions)
        seen = {item["name"] for item in merged.candidate_fields}
        for item in chunk_result.candidate_fields:
            if item["name"] in seen:
                conflicts.setdefault(item["name"], []).append(item)
                continue  # deterministic merge: first occurrence wins
            merged.candidate_fields.append(item)
            seen.add(item["name"])
        if archive_root is not None:
            chunk_dir = archive_root / run_id / "chunks" / f"chunk-{index}"
            chunk_dir.mkdir(parents=True, exist_ok=True)
            (chunk_dir / "request.md").write_text(prompt, encoding="utf-8")
            (chunk_dir / "response.md").write_text(response, encoding="utf-8")

    for name, items in conflicts.items():
        first = next((i for i in merged.candidate_fields if i["name"] == name), None)
        values = [str(first.get("value")) if first else "?"] + [
            str(i.get("value")) for i in items
        ]
        pages_seen = ([int(first.get("page", 0))] if first else []) + [
            int(i.get("page", 0)) for i in items
        ]
        merged.contradictions.append(
            f"تناقض «{name}»: مقادیر {' مقابل '.join(dict.fromkeys(values))}"
            f" در صفحات {', '.join(str(p) for p in dict.fromkeys(pages_seen))}"
            " — مقدار نخست نگه داشته شد؛ بازبینی لازم است."
        )

    # 'Complete' means page accounting is closed (review P1): every page
    # was eligible and every chunk validated. Contradictions are surfaced
    # for human review and do not by themselves block the claim.
    complete = (
        not omitted
        and not merged.issues
        and bool(eligible)
        and set(eligible) == set(range(1, page_count + 1))
    )
    if archive_root is not None:
        run_dir = archive_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "merge.md").write_text(
            "# ادغام چانک‌ها\n\n"
            f"- چانک‌ها: {len(chunk_reports)}\n"
            "- صفحات حذف‌شده: "
            + (", ".join(map(str, omitted)) or "—")
            + f"\n- تناقض‌ها: {len(conflicts)}\n\n## فیلدهای نهایی\n"
            + "\n".join(
                f"- {item['name']} = {item.get('value')} (صفحه {item.get('page')})"
                for item in merged.candidate_fields
            ),
            encoding="utf-8",
        )
        (run_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "prompt_version": PROMPT_VERSION,
                    "provider": provider,
                    "model": model,
                    "source_hash": source_hash,
                    "chunks": len(chunk_reports),
                    "chunk_reports": chunk_reports,
                    "omitted_pages": omitted,
                    "complete": complete,
                    "validation_ok": merged.ok,
                    "contradictions": merged.contradictions,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    merged.contradictions = list(dict.fromkeys(merged.contradictions))

    return CompleteExtraction(
        result=merged,
        omitted_pages=omitted,
        complete=complete,
        chunk_count=len(chunk_reports),
    )


def accepted_profile(
    result: ExtractionResult,
    *,
    accepted_names: set[str],
    source_hash: str,
    manufacturer: str = "",
    part_number: str = "",
) -> ControllerProfile:
    """Build the reusable profile from ONLY the explicitly accepted fields."""

    fields: list[EvidenceField] = []
    for item in result.candidate_fields:
        if item["name"] not in accepted_names:
            continue
        spec = FIELD_SPECS[item["name"]]
        value = item.get("value")
        if spec.kind == "number":
            value = float(value)
        fields.append(
            EvidenceField(
                name=item["name"],
                value=value,
                unit=str(item.get("unit", "") or spec.unit),
                value_min=item.get("value_min"),
                value_typ=item.get("value_typ"),
                value_max=item.get("value_max"),
                conditions=str(item.get("conditions", "") or ""),
                provenance=Provenance(
                    source_hash=source_hash,
                    page=int(item.get("page", 1)),
                    table_or_figure=str(item.get("table_or_figure", "") or ""),
                    extractor_version=f"ai:{PROMPT_VERSION}:{result.run_id}",
                    confidence=(
                        float(item["confidence"])
                        if isinstance(item.get("confidence"), (int, float))
                        and 0 <= float(item["confidence"]) <= 1
                        else None
                    ),
                ),
                review_state="extracted",
            )
        )
    return ControllerProfile.from_extraction(
        manufacturer=manufacturer or result.manufacturer or "unknown",
        part_number=part_number or result.part_number or "unknown",
        source_object_sha256=source_hash,
        profile_version=f"ai-{result.run_id}",
        package=result.package,
        fields=tuple(fields),
        contradictions=tuple(result.contradictions),
        unknown_facts=tuple(result.unknown_facts),
        notes="دست‌چین‌شده از پاسخ AI؛ نیازمند بازبینی انسانی پیش از استفادهٔ مهندسی.",
    )


def archive_run(
    vault_path_getter: Callable[[], str],
    *,
    run_id: str,
    request_text: str,
    response_text: str,
    result: ExtractionResult,
    source_hash: str,
    provider: str,
    model: str,
) -> Path | None:
    """Store request/response/metadata under the vault's ai-runs/ folder."""

    raw = (vault_path_getter() or "").strip()
    if not raw:
        return None
    folder = Path(raw) / "ai-runs" / run_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "request.md").write_text(request_text, encoding="utf-8")
    (folder / "response.md").write_text(response_text, encoding="utf-8")
    (folder / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "prompt_version": PROMPT_VERSION,
                "provider": provider,
                "model": model,
                "source_hash": source_hash,
                "validation_ok": result.ok,
                "issues": [i.__dict__ for i in result.issues],
                "accepted_candidates": [f["name"] for f in result.candidate_fields],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return folder
