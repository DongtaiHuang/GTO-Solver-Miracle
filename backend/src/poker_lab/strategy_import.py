"""Trusted local CLI only. Never expose this workflow as a public upload endpoint."""

import argparse
import sqlite3
from pathlib import Path

from poker_lab.strategy_catalog import import_dataset, read_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--approve-gto", action="store_true")
    parser.add_argument("--reviewer")
    parser.add_argument("--review-evidence")
    parser.add_argument("--confirm-source-and-rights", action="store_true")
    args = parser.parse_args()
    if args.approve_gto and not (
        args.reviewer and args.review_evidence and args.confirm_source_and_rights
    ):
        parser.error("Approval needs --reviewer, --review-evidence and --confirm-source-and-rights")
    if not args.approve_gto and (
        args.reviewer or args.review_evidence or args.confirm_source_and_rights
    ):
        parser.error("Review flags require explicit --approve-gto")
    try:
        count = import_dataset(
            read_dataset(args.dataset),
            args.catalog,
            reviewer=args.reviewer if args.approve_gto else None,
            evidence=args.review_evidence,
            confirm_rights=args.confirm_source_and_rights,
        )
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f"Import rejected: {exc}\n")
    print(
        f"Imported {count} solution(s) transactionally. Structural checks are not mathematical validation."
    )


if __name__ == "__main__":
    main()
