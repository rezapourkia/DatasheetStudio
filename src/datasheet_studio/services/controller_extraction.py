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


def build_user_message(
    part_number: str, page_texts: dict[int, str], max_pages: int = 40
) -> str:
    allowed = "\n".join(
        f"- {spec.name} [{spec.unit or 'enum'}]"
        + (f" (one of: {', '.join(spec.enum_values)})" if spec.enum_values else "")
        for spec in FIELD_SPECS.values()
    )
    pages = sorted(page_texts)[:max_pages]
    context = "\n\n".join(
        f"<!-- page:{number} -->\n{page_texts[number][:4000]}" for number in pages
    )
    return (
        f"Extract the controller profile for part «{part_number or 'unknown'}».\n\n"
        f"Allowed fields (name [unit]):\n{allowed}\n\n"
        f"Document text with page markers:\n{context}\n\n"
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
