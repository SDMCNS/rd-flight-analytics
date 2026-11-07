"""Command line interface: ``ectl prepare | etl | run``."""

from __future__ import annotations

import argparse
import logging

from .etl import run_etl
from .prepare import prepare


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="ectl", description="EUROCONTROL R&D flight data tools")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("prepare", help="extract .gz files and standardise filenames")
    sp.add_argument("data_dir", nargs="?", default=".")

    for name, help_ in (("etl", "build SQLite db from standardised CSVs"), ("run", "prepare + etl")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("data_dir", nargs="?", default=".")
        s.add_argument("--db", default="flights.db", help="output SQLite path (default: flights.db)")

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(levelname)s %(message)s")

    if a.cmd in ("prepare", "run"):
        prepare(a.data_dir)
    if a.cmd in ("etl", "run"):
        run_etl(a.data_dir, a.db)


if __name__ == "__main__":
    main()

