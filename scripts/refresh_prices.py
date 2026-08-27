"""Fetch Cursor model pricing docs and regenerate prices.json."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from prices import fetch_and_save_prices  # noqa: E402


def main():
    payload = fetch_and_save_prices()
    print(f"Wrote {len(payload['models'])} models to {ROOT / 'prices.json'}")


if __name__ == "__main__":
    main()
