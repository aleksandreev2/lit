# Chapter promotion transaction

Promotion is the only operation that may advance a chapter from `AUTHOR_APPROVED` to `HAPPENED` and move runtime authority to the next `NOT_STARTED` chapter.

## Non-negotiable approval rule

There is no `--author-approved` switch and CI success is not approval evidence.

A promotion package must contain a separate JSON artifact matching `schemas/author_approval_evidence.schema.json` with:

- stable `SB-APP-*` evidence ID;
- `approver_role: AUTHOR`;
- `source_type: EXPLICIT_AUTHOR_ACTION`;
- exact SHA-256 of the verified freeze manifest;
- exact SHA-256 of the frozen chapter text;
- explicit source context and timestamp.

The current chapter manifest must already be `AUTHOR_APPROVED` and reference the same evidence ID. The current runtime must also report `AUTHOR_APPROVED`.

## Promotion package

A `promotion-plan.json` points to package-local files:

- verified cryptographic freeze manifest;
- explicit author approval evidence;
- declared chapter delta bound to the frozen chapter hash;
- candidate next runtime snapshot;
- candidate structured state snapshot;
- candidate System snapshot;
- candidate active-arc snapshot;
- next chapter manifest.

Candidate snapshots are fully validated before any authority file is touched. The candidate runtime must advance `through_chapter` and `last_approved_chapter` to the promoted chapter and create exactly `chapter + 1` as `NOT_STARTED`. Structured state and active-arc pointers must advance to the same promoted chapter.

## Command

Validation only:

```bash
python scripts/promote_chapter.py promotion-plan.json --root /path/to/repository --validate-only
```

Promotion:

```bash
python scripts/promote_chapter.py promotion-plan.json --root /path/to/repository
```

The real repository cannot promote chapter 25 yet: `current/025` is still `NOT_STARTED` and has no chapter text, freeze, delta, or explicit approval artifact.

## Transaction behavior

After every input and cross-file invariant passes, the command applies one failure-atomic logical transaction:

1. acquire an exclusive promotion lock;
2. stage replacement bytes and capture original authority bytes;
3. replace runtime/state/System/active-arc snapshots;
4. archive the approved current manifest as `HAPPENED`;
5. remove the old current manifest;
6. create the next `NOT_STARTED` manifest;
7. write a cryptographic promotion report;
8. on any raised failure, restore every original file and remove every newly-created target before releasing the lock.

This protects against process-level write failures and exceptions. A normal filesystem cannot provide a single hardware-atomic rename covering eight independent files; crash-level durability would require a persistent recovery journal or transactional storage. The implementation therefore makes the exact guarantee explicit instead of overstating it.

## Promotion report

`promotion/<chapter>.json` binds:

- freeze manifest hash;
- frozen chapter hash;
- author approval ID;
- chapter delta hash;
- candidate runtime/state/System/active-arc/next-manifest hashes;
- resulting next chapter number.

The report is itself part of the same transaction.

## Tests

`tests/test_promotion.py` uses only synthetic temporary repositories and proves:

- valid approval-gated promotion advances all authorities together;
- missing approval blocks without mutation;
- approval must bind the exact freeze hash;
- chapter delta must bind the exact frozen text hash;
- an injected mid-commit failure restores every original authority and leaves no archive, next chapter, report, or lock behind.

No Ch25 prose is created or consumed by these tests.
