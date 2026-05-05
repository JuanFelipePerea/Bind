"""
Nuclear migration reset script.

Run this ONCE after pointing DATABASE_URL at your Neon database:
    python reset_migrations.py

What it does:
  1. Deletes db.sqlite3 (local SQLite file)
  2. Wipes every migration file in accounts/, events/, modules/ (keeps __init__.py)
  3. Runs makemigrations for all apps
  4. Runs migrate against whatever DATABASE_URL is set to
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
APPS = ['accounts', 'events', 'modules']


def confirm(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N] ").strip().lower()
    return answer == 'y'


def delete_sqlite():
    db = BASE_DIR / 'db.sqlite3'
    if db.exists():
        db.unlink()
        print(f"  Deleted {db}")
    else:
        print("  db.sqlite3 not found — skipping.")


def wipe_migrations():
    for app in APPS:
        migrations_dir = BASE_DIR / app / 'migrations'
        if not migrations_dir.exists():
            print(f"  {app}/migrations/ not found — skipping.")
            continue
        removed = 0
        for f in migrations_dir.iterdir():
            if f.name != '__init__.py' and f.suffix == '.py':
                f.unlink()
                removed += 1
            elif f.is_dir() and f.name == '__pycache__':
                shutil.rmtree(f)
        print(f"  {app}/migrations/ — removed {removed} migration file(s).")


def run(cmd: list[str]):
    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        print(f"\nERROR: command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


if __name__ == '__main__':
    print("=" * 60)
    print("  BIND — Nuclear Migration Reset")
    print("=" * 60)

    database_url = os.environ.get('DATABASE_URL', '')
    if not database_url:
        # Try loading from .env
        try:
            from dotenv import load_dotenv
            load_dotenv()
            database_url = os.environ.get('DATABASE_URL', '')
        except ImportError:
            pass

    if not database_url:
        print("\nWARNING: DATABASE_URL is not set.")
        print("Set it in your .env file before running this script.\n")
        if not confirm("Continue anyway (will use SQLite fallback)?"):
            sys.exit(0)
    else:
        print(f"\nTarget database: {database_url[:40]}...")

    print()
    if not confirm("This will DELETE all local migrations and db.sqlite3. Proceed?"):
        print("Aborted.")
        sys.exit(0)

    print("\n[1/4] Deleting db.sqlite3...")
    delete_sqlite()

    print("\n[2/4] Wiping migration files...")
    wipe_migrations()

    print("\n[3/4] Running makemigrations...")
    run([sys.executable, 'manage.py', 'makemigrations'] + APPS)

    print("\n[4/4] Running migrate...")
    run([sys.executable, 'manage.py', 'migrate'])

    print("\nDone. Your Neon database is ready.")
