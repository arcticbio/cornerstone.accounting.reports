# Golden labels — 2026-06

One JSON file per property. Each labels every page of every input document in the June 2026
bundle with its section id, continuation flag and record qualifier, and names the schema and
output definition that apply.

- `documents[].file` is relative to `settings.bundle_root` (default `data/bundle/2026-06`).
- Missoula and Cobalt labels were derived from the report name printed in each page's footer
  and are exact.
- McCathren labels were derived by page offset from the published packages (the baselines have
  no text layer). Two pages were spot-checked visually. **Phase 1 performs the full visual
  verification** and corrects these files if needed.
- `expected_output` (the composer's expected page sequence) is generated and committed in
  Phase 2 from the output definitions, then frozen.

Page object keys: `page` (1-based), `section` (schema section id), `continuation` (bool),
`record` — the **mapped record id** from `config/properties.yaml`, or `null`. For single-record
properties `null` means the default record (SPEC §5 rule 3). Optional `orientation` (one of
`upright`, `rotated_90_cw`, `rotated_90_ccw`, `rotated_180`) records how the content is turned
*as the classifier sees it*, i.e. after OCR's `--rotate-pages` for scanned sources; eval scores
orientation only on pages that carry the key.

`expected_output` shape (frozen in Phase 2): a list with one entry per output page, in order —
`{"output_page": n, "doc_role": ..., "section": ..., "record": <record id or null>, "source_page": n}`.

These files are the few-shot exemplar source for the classifier (SPEC §7.2) and the ground
truth for `crr eval` (SPEC §8). Treat them as code: changes go through PR review.
