# Google Drive ↔ GitHub sync contract

Production Engine v2 does not use blind bidirectional sync.

GitHub stores structured machine state; Google Drive contains human-facing project documents and source material. A filename/title resemblance is not enough to decide authority or overwrite direction.

## Registered mappings

`sync/manifest.yaml` currently records two high-confidence project pairs discovered through the connected Google Drive account:

1. `canon/system.yaml` ↔ Drive document `Система богатства — правила, квоты и прогрессия`;
2. `canon/active_arc.yaml` ↔ Drive document `00_ACTIVE_ARC_STATE_AND_FORWARD_PLAN — Система богатства`.

Both are `MANUAL_ONLY`, `authority_owner: MANUAL`, `last_sync_at: null`, and start with `conflict_state: UNKNOWN`. The manifest records the observed GitHub content SHA-256/revision and Drive file/revision IDs, but this is a baseline observation, **not** a claim that the two representations are byte-equivalent or previously synchronized.

## Conflict detection

`scripts/sync_conflicts.py` compares a manifest baseline with an observation snapshot and classifies each mapping as:

- `CLEAN`;
- `GITHUB_CHANGED`;
- `DRIVE_CHANGED`;
- `BOTH_CHANGED`;
- `UNKNOWN`.

Example observation file:

```json
{
  "entries": {
    "SB-SYNC-SYSTEM-RULES": {
      "github_sha256": "<64 hex>",
      "drive_revision": "12",
      "drive_sha256": null
    }
  }
}
```

Run:

```bash
python scripts/sync_conflicts.py sync/manifest.yaml \
  --observations observed.json \
  --output sync-status.json \
  --fail-on-conflict
```

Without a live Drive revision observation, the result is `UNKNOWN`, never `CLEAN`. This is intentional: CI must not infer that Drive is unchanged merely because it cannot query Drive.

## Write policy

The current checker performs **zero writes** to GitHub or Drive and every result carries `automatic_write_allowed: false`.

Future write automation must be explicit and directional. Before any write adapter is introduced it must:

1. refresh both GitHub and Drive observations;
2. reject `BOTH_CHANGED`;
3. verify the mapping's permitted direction and authority owner;
4. create a new post-write baseline only after the destination revision/hash is confirmed;
5. never use title-only matching after a stable Drive file ID is known.

No Drive file was modified while adding this contract.
