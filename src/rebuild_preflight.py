"""Conservative disk projection for a complete provenance-first v2 release."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

GIB = 1024**3
BASE_DB_TO_RAW_RATIO = 0.60
ENRICHMENT_OVERHEAD_RATIO = 0.30
BMF_REGISTRY_TO_CSV_RATIO = 2.30
MIN_BMF_REGISTRY_BYTES = 750_219_264
MIN_SCRATCH_BYTES = 8 * GIB
EXPORT_ALLOWANCE_BYTES = 512 * 1024**2
SAFETY_RESERVE_BYTES = 2 * GIB


def directory_bytes(path: Path, pattern: str) -> int:
    return sum(item.stat().st_size for item in path.glob(pattern) if item.is_file())


@dataclass(frozen=True)
class DiskProjection:
    raw_bytes: int
    legacy_db_bytes: int
    bmf_csv_bytes: int
    v2_db_bytes: int
    bmf_registry_bytes: int
    export_bytes: int
    scratch_bytes: int
    safety_reserve_bytes: int
    available_bytes: int

    @property
    def incremental_bytes(self) -> int:
        return (
            self.v2_db_bytes
            + self.bmf_registry_bytes
            + self.export_bytes
            + self.scratch_bytes
            + self.safety_reserve_bytes
        )

    @property
    def projected_peak_bytes(self) -> int:
        return self.raw_bytes + self.legacy_db_bytes + self.bmf_csv_bytes + self.incremental_bytes

    @property
    def fits(self) -> bool:
        return self.available_bytes >= self.incremental_bytes


def project_disk(raw_dir: Path, output: Path, bmf_dir: Path) -> DiskProjection:
    raw_bytes = directory_bytes(raw_dir, "*.xml")
    legacy = Path("data/grants.db")
    legacy_bytes = legacy.stat().st_size if legacy.exists() else 0
    bmf_csv_bytes = directory_bytes(bmf_dir, "eo[1-4].csv")
    base_db = int(raw_bytes * BASE_DB_TO_RAW_RATIO)
    v2_db = int(base_db * (1 + ENRICHMENT_OVERHEAD_RATIO))
    bmf_registry = max(int(bmf_csv_bytes * BMF_REGISTRY_TO_CSV_RATIO), MIN_BMF_REGISTRY_BYTES)
    scratch = max(MIN_SCRATCH_BYTES, int(v2_db * 0.75))
    available = shutil.disk_usage(output.parent).free
    return DiskProjection(
        raw_bytes,
        legacy_bytes,
        bmf_csv_bytes,
        v2_db,
        bmf_registry,
        EXPORT_ALLOWANCE_BYTES,
        scratch,
        SAFETY_RESERVE_BYTES,
        available,
    )


def gib(value: int) -> str:
    return f"{value / GIB:,.1f} GiB"


def print_projection(projection: DiskProjection) -> None:
    print("V2 disk preflight")
    print(f"  Existing raw XML:              {gib(projection.raw_bytes)}")
    print(f"  Existing legacy database:      {gib(projection.legacy_db_bytes)}")
    print(f"  Existing BMF source CSVs:      {gib(projection.bmf_csv_bytes)}")
    print(f"  Projected v2 database:         {gib(projection.v2_db_bytes)}")
    print(f"  Projected BMF registry:        {gib(projection.bmf_registry_bytes)}")
    print(f"  Export allowance:              {gib(projection.export_bytes)}")
    print(f"  SQLite/index scratch:          {gib(projection.scratch_bytes)}")
    print(f"  Safety reserve:                {gib(projection.safety_reserve_bytes)}")
    print(f"  Required additional free:      {gib(projection.incremental_bytes)}")
    print(f"  Projected peak footprint:      {gib(projection.projected_peak_bytes)}")
    print(f"  Currently available:           {gib(projection.available_bytes)}")
    print(f"  Result: {'PASS' if projection.fits else 'FAIL'}")


def require_capacity(raw_dir: Path, output: Path, bmf_dir: Path) -> DiskProjection:
    projection = project_disk(raw_dir, output, bmf_dir)
    print_projection(projection)
    if not projection.fits:
        raise RuntimeError(
            "Unsafe full rebuild: projected working set exceeds available disk space."
        )
    return projection
