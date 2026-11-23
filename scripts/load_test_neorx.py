"""Small reproducible HTTP concurrency test for the locally deployed NeoRX stack."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import time
from urllib.request import Request, urlopen


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[position]


def request_once(url: str, timeout: float) -> tuple[bool, float, int | None]:
    started = time.perf_counter()
    try:
        request = Request(url, headers={"User-Agent": "NeoRX-load-test/1.0"})
        with urlopen(request, timeout=timeout) as response:
            response.read()
            status = response.status
        return 200 <= status < 400, time.perf_counter() - started, status
    except Exception:
        return False, time.perf_counter() - started, None


def run_level(url: str, users: int, requests_per_user: int, timeout: float) -> dict:
    total = users * requests_per_user
    started = time.perf_counter()
    rows: list[tuple[bool, float, int | None]] = []
    with ThreadPoolExecutor(max_workers=users) as pool:
        futures = [pool.submit(request_once, url, timeout) for _ in range(total)]
        for future in as_completed(futures):
            rows.append(future.result())
    elapsed = time.perf_counter() - started
    latencies = [row[1] * 1000 for row in rows]
    successful = sum(row[0] for row in rows)
    return {
        "concurrent_users": users,
        "requests": total,
        "successful": successful,
        "failed": total - successful,
        "success_rate_percent": round(successful * 100 / total, 2),
        "elapsed_seconds": round(elapsed, 3),
        "throughput_requests_per_second": round(total / elapsed, 2),
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 2),
            "p50": round(percentile(latencies, 0.50), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "maximum": round(max(latencies), 2),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requests-per-user", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    targets = {
        "frontend_estatico": "/",
        "salud_api_y_base_datos": "/health/",
    }
    levels = [10, 25, 50, 100]
    report = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "method": "closed concurrency with one HTTP request at a time per simulated user",
        "requests_per_user": args.requests_per_user,
        "targets": {},
        "scope_note": (
            "This test measures the static web entry point and the public health endpoint, "
            "which verifies database connectivity. It does not measure DICOM upload or CNN inference."
        ),
    }
    for name, path in targets.items():
        url = args.base_url.rstrip("/") + path
        report["targets"][name] = [
            run_level(url, users, args.requests_per_user, args.timeout) for users in levels
        ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
