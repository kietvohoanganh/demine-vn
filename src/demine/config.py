"""Minimal configuration for the final strict-real workflow."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class GridConfig:
    cell_size_m: float = 100.0
    n_cells_x: int = 220
    n_cells_y: int = 180
    origin_lon: float = 106.85
    origin_lat: float = 16.72

@dataclass
class StrictRealConfig:
    record_kernel_radius_m: float = 180.0
