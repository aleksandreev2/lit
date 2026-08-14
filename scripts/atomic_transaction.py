#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileOperation:
    target: Path
    content: bytes | None


def _safe_relative(root: Path, target: Path) -> Path:
    root = root.resolve()
    target = target.resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"transaction target escapes root: {target}")
    return target.relative_to(root)


def apply_failure_atomic(
    root: Path,
    operations: list[FileOperation],
    *,
    fault_after: int | None = None,
) -> None:
    """Apply a multi-file logical transaction with rollback on any process-level failure.

    This is failure-atomic for exceptions raised while the process is alive. A journal and backups are
    retained until commit completes, making an interrupted transaction inspectable rather than silently
    accepted as authoritative state.
    """
    root = root.resolve()
    lock_path = root / ".production-promotion.lock"
    txn_root = root / ".promotion-txn"
    txn_id = uuid.uuid4().hex
    txn_dir = txn_root / txn_id
    backup_dir = txn_dir / "backup"
    stage_dir = txn_dir / "stage"

    lock_fd: int | None = None
    snapshots: dict[Path, bytes | None] = {}
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(lock_fd, txn_id.encode("ascii"))
        os.fsync(lock_fd)

        txn_dir.mkdir(parents=True, exist_ok=False)
        backup_dir.mkdir()
        stage_dir.mkdir()

        journal_ops: list[dict] = []
        for index, operation in enumerate(operations):
            target = operation.target.resolve()
            relative = _safe_relative(root, target)
            original = target.read_bytes() if target.exists() else None
            snapshots[target] = original

            if original is not None:
                backup_path = backup_dir / f"{index:03d}.bin"
                backup_path.write_bytes(original)
                backup_name: str | None = backup_path.name
            else:
                backup_name = None

            if operation.content is not None:
                stage_path = stage_dir / f"{index:03d}.bin"
                stage_path.write_bytes(operation.content)
                stage_name: str | None = stage_path.name
            else:
                stage_name = None

            journal_ops.append(
                {
                    "target": str(relative),
                    "backup": backup_name,
                    "stage": stage_name,
                    "delete": operation.content is None,
                }
            )

        (txn_dir / "journal.json").write_text(
            json.dumps({"transaction": txn_id, "state": "PREPARED", "operations": journal_ops}, indent=2)
            + "\n",
            encoding="utf-8",
        )

        applied = 0
        for index, operation in enumerate(operations):
            target = operation.target.resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            if operation.content is None:
                target.unlink(missing_ok=True)
            else:
                staged = stage_dir / f"{index:03d}.bin"
                os.replace(staged, target)
            applied += 1
            if fault_after is not None and applied >= fault_after:
                raise RuntimeError(f"injected transaction failure after {applied} operation(s)")

        (txn_dir / "journal.json").write_text(
            json.dumps({"transaction": txn_id, "state": "COMMITTED", "operations": journal_ops}, indent=2)
            + "\n",
            encoding="utf-8",
        )
    except Exception:
        for target, original in snapshots.items():
            if original is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                restore = txn_dir / f"restore-{uuid.uuid4().hex}.bin"
                restore.write_bytes(original)
                os.replace(restore, target)
        raise
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        lock_path.unlink(missing_ok=True)
        if txn_dir.exists():
            shutil.rmtree(txn_dir, ignore_errors=True)
        if txn_root.exists() and not any(txn_root.iterdir()):
            txn_root.rmdir()
