# نمونهٔ رکورد مغناطیسی — هسته EE19/17 (فاز ۲)

> ⚠️ **این رکورد صرفاً نمایشی و تأییدنشده است.** ابعاد از داده‌های نمونهٔ
> قبلی فلای‌بک آمده‌اند؛ نه سازنده واقعی مشخص است و نه هیچ فیلدی `verified`
> است. نام «EE19» تا فاز کاتالوگ مغناطیسی فقط یک نام خانواده/مستعار است،
> نه رکورد سفارش‌پذیر.

قرارداد اسکیما: `docs/modules/KNOWLEDGE_BASE_SCHEMA.md`
فایل JSON معادل (منبع واحد تست‌ها): `tests/fixtures/knowledge_base/ee19_core_record.json`

```json
{
  "schema_version": 2,
  "record_kind": "magnetics-record",
  "record": {
    "manufacturer": "(بدون سازنده — نمونه)",
    "family": "EE19/17",
    "kind": "core",
    "designation": "EE19/17-illustrative",
    "fields": [
      {
        "name": "effective_area_ae_mm2",
        "value": 23.0,
        "unit": "mm²",
        "value_min": null,
        "value_typ": null,
        "value_max": null,
        "conditions": "",
        "provenance": {
          "source_hash": "8636c073d30e67252fbed480632a7537903bcd55431b1eaa18f16b503a0f8438",
          "page": 1,
          "table_or_figure": "Illustrative dimensions",
          "extractor_version": "phase2-example (manual fixture)",
          "imported_at": "2026-09-15T12:00:00+00:00",
          "confidence": 0.3
        },
        "review_state": "unreviewed",
        "reviewed_by": "",
        "reviewed_at": ""
      },
      {
        "name": "window_area_aw_mm2",
        "value": 30.0,
        "unit": "mm²",
        "value_min": null,
        "value_typ": null,
        "value_max": null,
        "conditions": "",
        "provenance": {
          "source_hash": "8636c073d30e67252fbed480632a7537903bcd55431b1eaa18f16b503a0f8438",
          "page": 1,
          "table_or_figure": "Illustrative dimensions",
          "extractor_version": "phase2-example (manual fixture)",
          "imported_at": "2026-09-15T12:00:00+00:00",
          "confidence": 0.3
        },
        "review_state": "unreviewed",
        "reviewed_by": "",
        "reviewed_at": ""
      },
      {
        "name": "effective_length_le_mm",
        "value": 40.0,
        "unit": "mm",
        "value_min": null,
        "value_typ": null,
        "value_max": null,
        "conditions": "",
        "provenance": {
          "source_hash": "8636c073d30e67252fbed480632a7537903bcd55431b1eaa18f16b503a0f8438",
          "page": 1,
          "table_or_figure": "Illustrative dimensions",
          "extractor_version": "phase2-example (manual fixture)",
          "imported_at": "2026-09-15T12:00:00+00:00",
          "confidence": 0.3
        },
        "review_state": "unreviewed",
        "reviewed_by": "",
        "reviewed_at": ""
      },
      {
        "name": "mean_length_per_turn_mlt_mm",
        "value": 42.0,
        "unit": "mm",
        "value_min": null,
        "value_typ": null,
        "value_max": null,
        "conditions": "",
        "provenance": {
          "source_hash": "8636c073d30e67252fbed480632a7537903bcd55431b1eaa18f16b503a0f8438",
          "page": 1,
          "table_or_figure": "Illustrative dimensions",
          "extractor_version": "phase2-example (manual fixture)",
          "imported_at": "2026-09-15T12:00:00+00:00",
          "confidence": 0.3
        },
        "review_state": "unreviewed",
        "reviewed_by": "",
        "reviewed_at": ""
      },
      {
        "name": "effective_volume_ve_mm3",
        "value": 920.0,
        "unit": "mm³",
        "value_min": null,
        "value_typ": null,
        "value_max": null,
        "conditions": "",
        "provenance": {
          "source_hash": "8636c073d30e67252fbed480632a7537903bcd55431b1eaa18f16b503a0f8438",
          "page": 1,
          "table_or_figure": "Illustrative dimensions",
          "extractor_version": "phase2-example (manual fixture)",
          "imported_at": "2026-09-15T12:00:00+00:00",
          "confidence": 0.3
        },
        "review_state": "unreviewed",
        "reviewed_by": "",
        "reviewed_at": ""
      },
      {
        "name": "saturation_flux_density_t",
        "value": 0.22,
        "unit": "T",
        "value_min": null,
        "value_typ": null,
        "value_max": null,
        "conditions": "",
        "provenance": {
          "source_hash": "8636c073d30e67252fbed480632a7537903bcd55431b1eaa18f16b503a0f8438",
          "page": 1,
          "table_or_figure": "Illustrative dimensions",
          "extractor_version": "phase2-example (manual fixture)",
          "imported_at": "2026-09-15T12:00:00+00:00",
          "confidence": 0.3
        },
        "review_state": "unreviewed",
        "reviewed_by": "",
        "reviewed_at": ""
      }
    ],
    "compatible_bobbins": [
      "EE19-bobbin-illustrative"
    ],
    "aliases": [],
    "notes": "هستهٔ نمونهٔ فاز ۲؛ ابعاد از داده‌های تصویری قبلی فلای‌بک آمده و تأییدنشده است."
  }
}
```

## نکات بازبینی

1. تمام فیلدهای هندسی (`Ae`, `Aw`, `le`, `MLT`, `Ve`, `Bmax`) ساختار
   value/unit/min-typ-max و سندیت یکسان دارند.
2. وضعیت همه `unreviewed` است — این داده‌ها هرگز به‌عنوان دادهٔ تأییدشده
   در محاسبات استفاده نمی‌شوند مگر پس از بازبینی انسانی.
3. در فاز کاتالوگ واقعی (فاز ۱۲)، این رکورد با کد سفارش دقیق سازنده،
   بوبین سازگار و domain معتبر منحنی تلفات جایگزین می‌شود.
