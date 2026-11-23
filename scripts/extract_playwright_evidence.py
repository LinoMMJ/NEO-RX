"""Extract named screenshot attachments from a Playwright JSON report."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import re


def safe_name(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z._-]+", "-", value.strip()).strip("-")
    return value or "attachment"


def walk_suite(suite: dict, rows: list[dict]) -> None:
    for spec in suite.get("specs", []):
        for test in spec.get("tests", []):
            for result in test.get("results", []):
                for attachment in result.get("attachments", []):
                    if attachment.get("contentType") == "image/png" and attachment.get("body"):
                        rows.append(
                            {
                                "spec": spec.get("title", ""),
                                "test_status": result.get("status", ""),
                                "name": attachment.get("name", "screenshot"),
                                "body": attachment["body"],
                            }
                        )
    for child in suite.get("suites", []):
        walk_suite(child, rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for suite in report.get("suites", []):
        walk_suite(suite, rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, row in enumerate(rows, 1):
        filename = f"{index:02d}_{safe_name(row['name'])}.png"
        (args.output_dir / filename).write_bytes(base64.b64decode(row.pop("body")))
        manifest.append({**row, "file": filename})

    stats = report.get("stats", {})
    summary = {
        "stats": stats,
        "screenshots": manifest,
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
