# Page records

Browsing is the interface. Records are the reference material it leaves behind.

Open **Page details → Generation record** to inspect the current page's trace, or **Export record (JSON)** for a local, machine-readable bundle. Export HTML produces a usable standalone document with local controls; onward imagined navigation requires Elsewhere.

## Version 1

The JSON bundle has these fields:

| Field | Meaning |
| --- | --- |
| `schema` | `elsewhere.page-record` |
| `schema_version` | `1`; consumers should check this before interpreting fields |
| `exported_at` | Unix timestamp of the export |
| `page` | Stored page snapshot, including sanitized HTML, title, entry, model/provider, parent ID, site context, review and layout measurements when available |
| `generation` | Original trace, or `null` if an older page has no trace |
| `stored_html_sha256` | SHA-256 of the UTF-8 `page.html` string |
| `notes` | Interpretation and privacy notes |

New generation traces include `original_html` and `original_sha256`, optional `repair_html` / `repair_sha256` and repair reasons, `parent_id`, clicked `link`, continuity `context`, model/provider, instructions, sampling, timing, available usage, and `source_sha256` fingerprints of the generation/rendering application files. These fingerprints identify code content, not a guarantee of identical results. `partial_html` and the pipeline `phase` retain available output on errors/cancellation; a completed non-HTML cloud response can also be retained there with `failed_response_stats`.

The original response is written before sanitation or review. A completed trace is written before a page becomes available to bookmark. Page and trace are retained together by bookmarks and survive history clearing. Unbookmarking restores durable history. History and bookmarks do not automatically alter the model's weights.

## Original output versus rendered page

`generation.original_html` is the response returned by the inference adapter. A refinement is separate. `page.html` is the stored sanitized document with app-supplied baseline styling and trusted interactions. The original response can contain unsupported or unsafe markup: inspect it as text, rather than execute it.

When reopening a page, Elsewhere reapplies current sanitizer/controller fixes for safe browsing. Record export reads the stored snapshot directly instead. Browser-time DOM repairs, expanded sections, form values and scroll are not an archival DOM capture. Keep this distinction when evaluating outputs later. Older records can lack parent IDs, hashes or model metadata; the app does not fabricate them.

## Privacy and retention

Records contain prompts, generated source, linked-page excerpts and possibly user-entered form text. Export writes only to this installation's `exports` directory. No upload occurs; review content before sharing. API keys, backend session credentials and automatic machine paths are not included. Generated text can itself mention sensitive information, so exports are not anonymous by default.

Clear history removes unbookmarked page snapshots and traces, including failed-attempt traces. Bookmarks and exports remain. Evaluation runs from earlier versions remain separately on disk; no evaluator is part of the current application.
