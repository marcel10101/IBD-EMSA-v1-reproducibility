from __future__ import annotations

import json

from figure5_internal_common import FigureBuildError, VALIDATION_JSON, build_all


def main() -> None:
    try:
        validation = build_all()
    except FigureBuildError:
        raise
    if not validation.get("all_validation_passed"):
        print(json.dumps(validation, indent=2, ensure_ascii=False))
        raise SystemExit(1)
    print(f"Figure 5 internal validation build passed: {VALIDATION_JSON}")


if __name__ == "__main__":
    main()
