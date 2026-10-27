"""Create .env from .env.example with freshly generated random secrets.

Usage: python scripts/init_env.py [--force]
"""

import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"


def main() -> int:
    if TARGET.exists() and "--force" not in sys.argv:
        print(".env already exists; leaving it untouched (use --force to overwrite).")
        return 0

    generated: dict[str, str] = {}

    def secret_for(match: re.Match[str]) -> str:
        # The same placeholder gets the same secret everywhere (e.g. POSTGRES_PASSWORD
        # and the password inside DATABASE_URL stay in sync).
        return generated.setdefault(match.group(0), secrets.token_hex(12))

    TARGET.write_text(re.sub(r"change-me-[a-z]+", secret_for, EXAMPLE.read_text()))
    print(f"Created {TARGET.name} with {len(generated)} generated secrets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
