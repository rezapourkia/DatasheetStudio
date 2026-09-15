# نمونهٔ رکورد پروفایل قطعه — DK124 (فاز ۲)

> ⚠️ **این رکورد صرفاً نمایشی و تأییدنشده است.** هیچ فیلدی وضعیت `verified`
> ندارد؛ منبع هش‌شده یک placeholder است، نه PDF واقعی DK124. هدف این نمونه
> فقط بازبینی شکل و ساختار اسکیما توسط مالک پروژه است.

قرارداد اسکیما: `docs/modules/KNOWLEDGE_BASE_SCHEMA.md`
فایل JSON معادل (منبع واحد تست‌ها): `tests/fixtures/knowledge_base/dk124_profile.json`

```json
{
  "schema_version": 2,
  "record_kind": "component-profile",
  "record": {
    "manufacturer": "Linkage",
    "part_number": "DK124",
    "profile_version": "0.1-example",
    "source_object_sha256": "b3d226a41536cf9fb1715bb279f9a4f25c35acb05559a17dac5e6ffcb4859c4e",
    "source_revision": "v1.6",
    "package": "DIP-8",
    "device_type": "offline-switching-controller",
    "aliases": [
      {
        "value": "DK124B",
        "kind": "ordering-code",
        "note": ""
      }
    ],
    "fields": [
      {
        "name": "switching_frequency_khz",
        "value": 65,
        "unit": "kHz",
        "value_min": null,
        "value_typ": 65.0,
        "value_max": null,
        "conditions": "",
        "provenance": {
          "source_hash": "b3d226a41536cf9fb1715bb279f9a4f25c35acb05559a17dac5e6ffcb4859c4e",
          "page": 1,
          "table_or_figure": "Features",
          "extractor_version": "phase2-example (manual fixture)",
          "imported_at": "2026-09-15T12:00:00+00:00",
          "confidence": 0.6
        },
        "review_state": "extracted",
        "reviewed_by": "",
        "reviewed_at": ""
      },
      {
        "name": "current_limit_a",
        "value": 1.1,
        "unit": "A",
        "value_min": 1.1,
        "value_typ": null,
        "value_max": null,
        "conditions": "",
        "provenance": {
          "source_hash": "b3d226a41536cf9fb1715bb279f9a4f25c35acb05559a17dac5e6ffcb4859c4e",
          "page": 2,
          "table_or_figure": "Electrical Characteristics",
          "extractor_version": "phase2-example (manual fixture)",
          "imported_at": "2026-09-15T12:00:00+00:00",
          "confidence": 0.6
        },
        "review_state": "extracted",
        "reviewed_by": "",
        "reviewed_at": ""
      },
      {
        "name": "ovp_threshold_v",
        "value": 540,
        "unit": "V",
        "value_min": 540.0,
        "value_typ": null,
        "value_max": null,
        "conditions": "",
        "provenance": {
          "source_hash": "b3d226a41536cf9fb1715bb279f9a4f25c35acb05559a17dac5e6ffcb4859c4e",
          "page": 2,
          "table_or_figure": "Protection",
          "extractor_version": "phase2-example (manual fixture)",
          "imported_at": "2026-09-15T12:00:00+00:00",
          "confidence": 0.4
        },
        "review_state": "extracted",
        "reviewed_by": "",
        "reviewed_at": ""
      },
      {
        "name": "max_duty",
        "value": 0.7,
        "unit": "",
        "value_min": null,
        "value_typ": null,
        "value_max": 0.7,
        "conditions": "",
        "provenance": {
          "source_hash": "b3d226a41536cf9fb1715bb279f9a4f25c35acb05559a17dac5e6ffcb4859c4e",
          "page": 2,
          "table_or_figure": "Electrical Characteristics",
          "extractor_version": "phase2-example (manual fixture)",
          "imported_at": "2026-09-15T12:00:00+00:00",
          "confidence": 0.6
        },
        "review_state": "extracted",
        "reviewed_by": "",
        "reviewed_at": ""
      },
      {
        "name": "wide_range_power_w",
        "value": 18,
        "unit": "W",
        "value_min": null,
        "value_typ": 18.0,
        "value_max": null,
        "conditions": "",
        "provenance": {
          "source_hash": "b3d226a41536cf9fb1715bb279f9a4f25c35acb05559a17dac5e6ffcb4859c4e",
          "page": 1,
          "table_or_figure": "Features",
          "extractor_version": "phase2-example (manual fixture)",
          "imported_at": "2026-09-15T12:00:00+00:00",
          "confidence": 0.5
        },
        "review_state": "extracted",
        "reviewed_by": "",
        "reviewed_at": ""
      }
    ],
    "contradictions": [
      "جریان حدی در متن ۱.۱A و در جدول ۱.۲A ذکر شده؛ تا تطبیق با سند اصلی تعیین‌نشده."
    ],
    "unknown_facts": [
      "فرکانس در حالت سبک (light-load) نامشخص است."
    ],
    "notes": "پروفایل نمونهٔ فاز ۲؛ هیچ فیلدی verified نیست و برای استفادهٔ مهندسی تأیید نشده."
  }
}
```

## نکات بازبینی

1. هر فیلد مهندسی `Provenance` دارد: هش منبع، شماره صفحه، جدول/شکل، نسخه
   استخراج‌کننده، زمان درون‌ریزی و ضریب اطمینان.
2. وضعیت بازبینی همهٔ فیلدها `extracted` است — سقف مجاز برای درون‌ریزی
   خودکار/AI. ارتقا به `reviewed`/`verified` فقط با کار انسانی ممکن است.
3. تناقض‌ها (متن در برابر جدول) و واقعیت‌های مجهول به‌صورت صریح ذخیره
   می‌شوند، نه حذف.
