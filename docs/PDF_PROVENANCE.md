# PDF provenance and release evidence

PDF output is a downstream deliverable of an exact frozen chapter revision. It is not allowed to become an alternate text authority.

## Required bindings

A future release record matching `schemas/pdf_provenance.schema.json` binds:

- frozen source file + SHA-256;
- verified cryptographic freeze manifest + SHA-256;
- PDF file + SHA-256;
- technical-preflight evidence + SHA-256;
- visual-QA evidence + SHA-256;
- final deliverable status.

`python scripts/pdf_provenance_check.py pdf-provenance.json` verifies each file binding, re-runs the freeze verifier and confirms that the PDF record's frozen source hash matches the freeze manifest's `CHAPTER_TEXT` hash.

## Two independent gates

`deliverable_status: READY` is valid only when both gates are `PASS`:

1. **technical preflight** — file opens/parses, expected metadata/page structure/assets are present and other deterministic checks pass;
2. **visual QA** — rendered pages were actually inspected and the evidence is bound to the record.

A technical parser PASS cannot substitute for visual inspection. Conversely, a screenshot/image review cannot substitute for deterministic file validation.

Any change to the frozen source, freeze manifest, PDF, technical evidence, or visual evidence breaks the corresponding SHA binding.

## Current chapter

No chapter-25 PDF provenance record is created because chapter 25 is still `NOT_STARTED`: there is no chapter candidate, no freeze, and no PDF to validate. Tests use synthetic temporary files solely to prove the provenance rules.
