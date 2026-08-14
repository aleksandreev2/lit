# CI QA report artifact

Every Production Engine workflow run can emit one compact `qa-report` artifact instead of scattering the evidence only across console logs.

## Contents

`python scripts/qa_report.py qa-report --revision <git-sha>` generates:

- `summary.json` — machine summary with PASS/BLOCK/REVIEW counts, current chapter/stage, dependency SHA-256 values, generated-audit state, stale-evidence list, research warnings, freeze state and semantic-review state;
- `logs/project_preflight.log`;
- `logs/provenance.log`;
- `logs/regression_locks.log`;
- `logs/dependency_graph.log`;
- `logs/current_chapter_readiness.log`;
- `manifest.json` — SHA-256 and byte size for every report file except itself.

`python scripts/qa_report_check.py qa-report` verifies the summary schema and every manifest-bound file hash/size.

## Meaning of the current report

The repository currently has `through_chapter: 24` and chapter 25 is `NOT_STARTED`. A green infrastructure report therefore does **not** mean chapter 25 passed prose QA. The report explicitly records:

- current chapter readiness as `REVIEW`;
- semantic review as `NOT_RUN`;
- chapter QA artifacts as `NOT_RUN`;
- freeze status as `NOT_AVAILABLE`.

This prevents a successful infrastructure pipeline from being misread as literary/editorial approval.

## Failure behavior

The report generator records a failed deterministic sub-check as `BLOCK` but still writes the report. In GitHub Actions the report build/upload steps run with `always()` after dependency installation, so a failing required gate can still leave diagnostic evidence when generation itself remains possible.

The report is an evidence bundle, not an alternate authority. The individual blocking CI commands remain required gates.
