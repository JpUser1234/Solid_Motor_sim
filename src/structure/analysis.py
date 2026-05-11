"""
Structural checks for thin-walled pressure vessels and simple bolt analysis.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class ThinWallResult:
    hoop_stress_pa: float
    longitudinal_stress_pa: float
    safety_factor_hoop: Optional[float]
    safety_factor_long: Optional[float]


def thin_walled_vessel(pressure_pa: float, inner_radius_m: float, wall_thickness_m: float, material_yield_pa: Optional[float] = None) -> ThinWallResult:
    """
    Compute hoop and longitudinal stresses for a thin-walled cylinder under internal pressure.

    σ_hoop = p * r / t
    σ_long = p * r / (2 t)

    Returns safety factors if material_yield_pa provided.
    """
    if wall_thickness_m <= 0:
        raise ValueError("wall_thickness_m must be > 0")
    if inner_radius_m <= 0:
        raise ValueError("inner_radius_m must be > 0")

    hoop = pressure_pa * inner_radius_m / wall_thickness_m
    long = pressure_pa * inner_radius_m / (2.0 * wall_thickness_m)

    sf_hoop = None
    sf_long = None
    if material_yield_pa and material_yield_pa > 0:
        sf_hoop = material_yield_pa / hoop if hoop > 0 else math.inf
        sf_long = material_yield_pa / long if long > 0 else math.inf

    return ThinWallResult(hoop, long, sf_hoop, sf_long)


@dataclass
class BoltCheckResult:
    shear_per_bolt_n: float
    bearing_stress_pa: float
    adequate_shear: Optional[bool]
    adequate_bearing: Optional[bool]


def simple_bolt_analysis(total_axial_load_n: float, n_bolts: int, bolt_shear_strength_pa: Optional[float], bolt_shank_area_m2: Optional[float], bearing_area_m2: float) -> BoltCheckResult:
    """
    Very simplified bolt check: split axial shear load equally, compare shear capacity and bearing.

    - shear_per_bolt = total_axial_load / n_bolts
    - bearing_stress = shear_per_bolt / bearing_area
    """
    if n_bolts <= 0:
        raise ValueError("n_bolts must be > 0")
    share = total_axial_load_n / float(n_bolts)
    shear_capacity = None
    adequate_shear = None
    if bolt_shear_strength_pa and bolt_shank_area_m2:
        shear_capacity = bolt_shear_strength_pa * bolt_shank_area_m2
        adequate_shear = shear_capacity >= share
    bearing_stress = share / bearing_area_m2 if bearing_area_m2 > 0 else math.inf
    adequate_bearing = None
    if bolt_shank_area_m2 and bolt_shear_strength_pa:
        # crude comparison: bearing allowable ~ 1.5 * shear strength (very approximate)
        adequate_bearing = bearing_stress <= 1.5 * bolt_shear_strength_pa
    return BoltCheckResult(share, bearing_stress, adequate_shear, adequate_bearing)
