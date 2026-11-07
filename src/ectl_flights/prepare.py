"""Extract and standardise raw EUROCONTROL R&D download files."""

from __future__ import annotations

import gzip
import logging
import shutil
from pathlib import Path
from typing import Dict, Union

log = logging.getLogger(__name__)

PathLike = Union[str, Path]

#: Standard target filename -> glob pattern of the raw EUROCONTROL file.
FILE_PATTERNS: Dict[str, str] = {
    "flights_anonymized.csv": "Flight_Points_Actual_*.csv",
    "planned_flights_anonymized.csv": "Flight_Points_Filed_*.csv",
    "routes.csv": "Route_*.csv",
    "airports.csv": "airports*.csv",
    "fir.csv": "fir*.csv",
}
METADATA_TARGET = "flights.csv"


def extract_gz(data_dir: PathLike = ".") -> list[Path]:
    """Decompress every ``*.gz`` in ``data_dir`` that is not already extracted."""
    data_dir = Path(data_dir)
    out = []
    for gz_file in sorted(data_dir.glob("*.gz")):
        target = gz_file.with_suffix("")
        if not target.exists():
            log.info("Extracting %s -> %s", gz_file.name, target.name)
            with gzip.open(gz_file, "rb") as f_in, open(target, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        out.append(target)
    return out


def standardize(data_dir: PathLike = ".") -> Dict[str, Path]:
    """Copy raw files to the standard names expected by :func:`ectl_flights.etl.run_etl`.

    Returns a mapping of standard name -> path for every file found.
    """
    data_dir = Path(data_dir)
    found: Dict[str, Path] = {}
    for target, pattern in FILE_PATTERNS.items():
        matches = sorted(p for p in data_dir.glob(pattern) if p.name != target)
        dest = data_dir / target
        if matches:
            shutil.copy(matches[0], dest)
            log.info("Standardized %s -> %s", matches[0].name, target)
            found[target] = dest
        elif dest.exists():
            found[target] = dest
        else:
            log.warning("No file matching '%s' found for '%s'", pattern, target)

    meta = sorted(
        p for p in data_dir.glob("Flights_*.csv")
        if "Points" not in p.name and p.name != METADATA_TARGET
    )
    dest = data_dir / METADATA_TARGET
    if meta:
        shutil.copy(meta[0], dest)
        log.info("Standardized metadata %s -> %s", meta[0].name, METADATA_TARGET)
        found[METADATA_TARGET] = dest
    elif dest.exists():
        found[METADATA_TARGET] = dest
    else:
        log.warning("No metadata file matching 'Flights_*.csv' found")
    return found


def prepare(data_dir: PathLike = ".") -> Dict[str, Path]:
    """Extract ``.gz`` archives and standardise filenames in ``data_dir``."""
    extract_gz(data_dir)
    return standardize(data_dir)

