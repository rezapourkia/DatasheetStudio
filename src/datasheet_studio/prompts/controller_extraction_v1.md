# Controller Profile Extraction Prompt — v1

You are extracting a switching-controller IC profile from a datasheet.

Return ONLY a JSON object (no prose, no code fences) shaped as:

```json
{
  "manufacturer": "string",
  "part_number": "string",
  "package": "string (optional)",
  "fields": [
    {
      "name": "canonical field name (see allowed list)",
      "value": 123.4,
      "unit": "unit exactly as allowed for this field",
      "value_min": 123.4,
      "value_typ": 123.4,
      "value_max": 123.4,
      "page": 3,
      "table_or_figure": "Table 4 / Figure 2 (optional)",
      "conditions": "test conditions (optional)",
      "confidence": 0.8
    }
  ],
  "contradictions": ["..."],
  "unknown_facts": ["..."]
}
```

Rules:

1. Use ONLY the canonical field names and units from the allowed list given
   with the document context. Unknown names are rejected.
2. Every numeric field MUST carry its exact unit.
3. Every field MUST cite `page` — an integer page number where the value
   appears. Out-of-range citations are rejected.
4. min/typ/max: fill whichever the datasheet states; omit the rest.
5. Never invent values. If a field is not stated, omit it and, if notable,
   list it in `unknown_facts`.
6. If the document states conflicting values, pick neither as final — add
   the conflict to `contradictions` and cite both pages.
7. `confidence` in [0, 1] — your own certainty about the value/citation.
8. Keep the response complete; truncated JSON will be rejected.
