from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_alembic(args: list[str]) -> int:
    command = [sys.executable, "-m", "alembic", *args]
    try:
        completed = subprocess.run(command, cwd=ROOT, check=False)
        return completed.returncode
    except FileNotFoundError as exc:
        print(f"Errore: impossibile avviare Alembic: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(
            "Uso: python -m app.scripts.migrate <revision|upgrade|downgrade|current|history> [argomenti]",
            file=sys.stderr,
        )
        return 1

    command = args[0]
    if command == "revision":
        if len(args) < 2:
            print('Errore: il comando revision richiede un messaggio, ad esempio: revision "create users table"', file=sys.stderr)
            return 1
        message = " ".join(args[1:])
        return run_alembic(["revision", "--autogenerate", "-m", message])
    if command == "upgrade":
        target = args[1] if len(args) > 1 else "head"
        return run_alembic(["upgrade", target])
    if command == "downgrade":
        target = args[1] if len(args) > 1 else "-1"
        return run_alembic(["downgrade", target])
    if command == "current":
        return run_alembic(["current"])
    if command == "history":
        return run_alembic(["history"])

    print(f"Comando non supportato: {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
