"""Create or update .env with freshly generated random secrets.

Usage:
    python scripts/init_env.py           create .env, or add any variables missing from an
                                         existing .env (existing values are never changed)
    python scripts/init_env.py --force   overwrite .env completely (generates new secrets)
"""

import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"

PLACEHOLDER = re.compile(r"change-me-([a-z]+)")


def make_secret(kind: str) -> str:
    # JWT signing keys get 256 bits; passwords get 96 bits of URL-safe hex.
    return secrets.token_hex(32 if kind == "jwt" else 12)


def fill_placeholders(text: str, generated: dict[str, str]) -> str:
    # The same placeholder gets the same secret everywhere (e.g. POSTGRES_PASSWORD and the
    # password inside DATABASE_URL stay in sync).
    def replace(match: re.Match[str]) -> str:
        return generated.setdefault(match.group(0), make_secret(match.group(1)))

    return PLACEHOLDER.sub(replace, text)


def variable_name(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    return line.split("=", 1)[0].strip()


def main() -> int:
    force = "--force" in sys.argv
    example = EXAMPLE.read_text()

    if force or not TARGET.exists():
        generated: dict[str, str] = {}
        TARGET.write_text(fill_placeholders(example, generated))
        print(f"Created {TARGET.name} with {len(generated)} generated secrets.")
        return 0

    existing = TARGET.read_text()
    present = {name for line in existing.splitlines() if (name := variable_name(line))}
    missing = [
        line for line in example.splitlines() if (name := variable_name(line)) and name not in present
    ]
    if not missing:
        print(".env is up to date; nothing to add.")
        return 0

    # If DATABASE_URL has to be added it must use the password already in .env.
    generated: dict[str, str] = {}
    for line in existing.splitlines():
        if variable_name(line) == "POSTGRES_PASSWORD":
            generated["change-me-postgres"] = line.split("=", 1)[1].strip()
    added = fill_placeholders("\n".join(missing), generated)
    TARGET.write_text(existing.rstrip("\n") + "\n\n# Added by init_env.py\n" + added + "\n")
    names = ", ".join(variable_name(line) for line in missing)
    print(f"Added to {TARGET.name}: {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
