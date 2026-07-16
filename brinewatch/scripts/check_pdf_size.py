"""Verify the submission PDF exists and is below the 20 MB portal limit."""
from __future__ import annotations

import sys
from pathlib import Path

LIMIT_MB = 20.0


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else
                Path(__file__).resolve().parents[2] / "BrineWatch_PFH2026_Submission_Draft.pdf")
    if not path.exists():
        print(f"FAIL: {path} does not exist")
        return 1
    size_mb = path.stat().st_size / (1024 * 1024)
    ok = size_mb < LIMIT_MB
    print(f"{'OK' if ok else 'FAIL'}: {path.name} = {size_mb:.2f} MB "
          f"(limit {LIMIT_MB:.0f} MB)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
