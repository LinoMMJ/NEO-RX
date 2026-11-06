"""Scan reachable Git blobs without ever printing a suspected secret value."""

from __future__ import annotations

import re
import subprocess
import sys


RULES = {
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai-key": re.compile(rb"\bsk-[A-Za-z0-9_-]{20,}"),
    "google-api-key": re.compile(rb"\bAIza[0-9A-Za-z_-]{20,}"),
    "aws-access-key": re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
}
ASSIGNMENT = re.compile(
    rb"(?im)^\s*(SECRET_KEY|FERNET_KEY|POSTGRES_PASSWORD|EMAIL_HOST_PASSWORD|API_KEY)\s*=\s*([^\r\n#]+)"
)
SAFE_MARKERS = (
    b"${", b"os.getenv", b"change-me", b"your-", b"<config", b"<gener",
    b"placeholder", b"example", b"redacted", b"secure-password-here",
    b"generate_key", b"get_random_secret_key", b"django-insecure", b"dev-key",
    b"test-key", b"app-password", b"password-de-aplic", b"xxxx", b"tu-",
)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)


def main() -> int:
    findings: list[tuple[str, str, str]] = []
    objects: dict[str, set[str]] = {}
    for line in git("rev-list", "--objects", "--all").decode("utf-8", "replace").splitlines():
        oid, _, path = line.partition(" ")
        if path:
            objects.setdefault(oid, set()).add(path)

    for oid, paths in objects.items():
        try:
            if int(git("cat-file", "-s", oid)) > 2_000_000:
                continue
            content = git("cat-file", "-p", oid)
        except (subprocess.CalledProcessError, ValueError):
            continue
        for name, pattern in RULES.items():
            if pattern.search(content):
                for path in paths:
                    findings.append((oid[:12], path, name))
        for match in ASSIGNMENT.finditer(content):
            value = match.group(2).strip().strip(b"\"'").lower()
            test_or_example = any(
                part in path.lower()
                for path in paths
                for part in ("conftest", "test_", "tests/", ".env.example")
            )
            if value and not test_or_example and not any(marker in value for marker in SAFE_MARKERS):
                for path in paths:
                    findings.append((oid[:12], path, "credential-assignment"))

    findings = sorted(set(findings), key=lambda item: (item[1], item[2], item[0]))
    if findings:
        print("Posibles secretos encontrados (los valores se ocultan):")
        for oid, path, rule in findings:
            print(f"- {path} | objeto {oid} | regla {rule}")
        return 1
    print(f"Historial limpio: {len(objects)} blobs examinados; no se detectaron secretos de alta confianza.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
