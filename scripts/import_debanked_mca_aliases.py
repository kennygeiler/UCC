"""Import MCA UCC aliases from deBanked (live fetch or bundled CSV).

Usage::

    python -m scripts.import_debanked_mca_aliases
    python -m scripts.import_debanked_mca_aliases --live
    python -m scripts.import_debanked_mca_aliases --csv data/debanked_mca_aliases.csv
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.mca.debanked_import import import_debanked_mca_aliases


def main() -> None:
    parser = argparse.ArgumentParser(description="Import deBanked MCA UCC aliases")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Fetch table from debanked.com (default: bundled CSV)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to CSV override (company_name, alias_1..5)",
    )
    args = parser.parse_args()
    stats = asyncio.run(
        import_debanked_mca_aliases(
            use_live_fetch=args.live,
            csv_path=args.csv,
        )
    )
    print(
        f"deBanked import: added={stats.added} updated={stats.updated} "
        f"registered_agent={stats.registered_agent} skipped_empty={stats.skipped_empty}"
    )


if __name__ == "__main__":
    main()
