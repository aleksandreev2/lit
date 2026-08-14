#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from freeze_manifest import verify_manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compatibility entrypoint for cryptographic chapter freeze verification."
    )
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    errors, _ = verify_manifest(args.manifest)
    if errors:
        print("FREEZE_CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("FREEZE_CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
