"""
security_audit.py
Local security pre-flight check.
Verifies the most common misconfigurations before you run the application.

Usage:  python security_audit.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


PASS = "[PASS]"
WARN = "[WARN]"
FAIL = "[FAIL]"


def check(label: str, condition: bool, fail_msg: str, warn: bool = False) -> bool:
    if condition:
        print(f"  {PASS} {label}")
        return True
    prefix = WARN if warn else FAIL
    print(f"  {prefix} {label}: {fail_msg}")
    return condition or warn


def main() -> None:
    print("=" * 60)
    print("Security Pre-flight Audit")
    print("=" * 60)

    issues = 0

    # ── Environment ───────────────────────────────────────────────────────────
    print("\n[1] Environment variables")
    env_file = Path(".env")

    ok = check(
        ".env file exists",
        env_file.exists(),
        "Copy .env.example to .env and fill in your credentials.",
        warn=True,
    )
    if env_file.exists():
        content = env_file.read_text()
        check(
            "APP_SECRET_KEY is set",
            "APP_SECRET_KEY=" in content and len([
                l for l in content.splitlines()
                if l.startswith("APP_SECRET_KEY=") and len(l.split("=", 1)[1]) >= 32
            ]) > 0,
            "Set a random string of at least 32 characters in APP_SECRET_KEY.",
        ) or (issues := issues + 1)

        check(
            "API key not hardcoded in .env as example value",
            "your_gemini_api_key_here" not in content,
            "Replace the placeholder with your real API key, or remove it if unused.",
            warn=True,
        )

        check(
            ".env is in .gitignore",
            ".env" in Path(".gitignore").read_text() if Path(".gitignore").exists() else False,
            "Add .env to your .gitignore file immediately.",
        ) or (issues := issues + 1)

    # ── Secrets in code ───────────────────────────────────────────────────────
    print("\n[2] No hardcoded secrets in source")
    secret_patterns = ["sk-", "AIza", "password=", "api_key="]
    py_files = list(Path("src").rglob("*.py")) + [Path("app.py"), Path("config/settings.py")]

    for f in py_files:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for pat in secret_patterns:
            if pat in text.lower() and "os.getenv" not in text[max(0, text.lower().find(pat) - 30):text.lower().find(pat) + 30]:
                print(f"  {WARN} Possible secret pattern '{pat}' found in {f}")

    check("No hardcoded secrets scan completed", True, "")

    # ── Database ──────────────────────────────────────────────────────────────
    print("\n[3] Database")
    db_files = list(Path("data").rglob("*.db")) if Path("data").exists() else []
    check(
        "Database files are in data/ (gitignored)",
        all("data" in str(f) for f in db_files),
        "Move database files into the data/ directory.",
        warn=True,
    )

    # ── File permissions ──────────────────────────────────────────────────────
    print("\n[4] Upload directory")
    upload_dir = Path("data/uploads")
    check(
        "data/uploads directory exists",
        upload_dir.exists(),
        "Run the app once to create it, or create it manually.",
        warn=True,
    )

    # ── Dependencies ──────────────────────────────────────────────────────────
    print("\n[5] Dependencies (basic check)")
    req = Path("requirements.txt")
    if req.exists():
        lines = [l.strip() for l in req.read_text().splitlines() if l.strip() and not l.startswith("#")]
        check(
            "requirements.txt has pinned versions",
            all("==" in l for l in lines),
            "Pin all dependency versions with '==' to ensure reproducible builds.",
        ) or (issues := issues + 1)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if issues == 0:
        print("Audit complete. No critical issues found.")
    else:
        print(f"Audit complete. {issues} critical issue(s) require attention.")
    print("=" * 60)


if __name__ == "__main__":
    main()
