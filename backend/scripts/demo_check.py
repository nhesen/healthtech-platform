"""Read-only demo readiness check for a running backend."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    base = os.getenv("DEMO_BACKEND_URL", "http://localhost:8000").rstrip("/")
    request = urllib.request.Request(
        f"{base}/health/demo", headers={"X-Demo-User": "admin@demo.az"}
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.loads(response.read())
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        print(f"FAIL backend readiness endpoint: {exc}")
        return 1

    checks = dict(result.get("checks", {}))
    checks["local_cv_simulator"] = (Path(__file__).parents[2] / "cv_service" / "run_demo.py").exists()
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    ready = bool(result.get("ready")) and all(checks.values())
    print(f"{'PASS' if ready else 'FAIL'} demo pre-flight")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
