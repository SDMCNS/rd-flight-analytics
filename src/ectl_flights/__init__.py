"""Tools for repeated handling of EUROCONTROL R&D archive flight data.

Typical workflow::

    from ectl_flights import prepare, run_etl, FlightDB

    prepare("data/")                       # unzip + standardise raw files
    run_etl("data/", db_path="flights.db") # build the SQLite database
    db = FlightDB("flights.db")
    summary = db.summary()
"""

from .prepare import prepare
from .etl import run_etl, build_flight_summary
from .db import FlightDB
from . import geo, analytics

__all__ = ["prepare", "run_etl", "build_flight_summary", "FlightDB", "geo", "analytics"]
__version__ = "0.1.0"

