"""
nozzle/optimizer.py
-------------------
Nozzle design helper: find the optimal throat diameter given a target average
thrust (or a target chamber pressure), a propellant, and a grain geometry.

Approach
--------
For a BATES grain the quasi-steady equilibrium pressure is:

    Pc = (ρp · a · ηc* · c* · Ab/At)^(1/(1-n))

and thrust:

    F  = ηCF · CF(Pc, Pa, γ) · Pc · At

Given a target F_avg or Pc_avg, we solve for At (and hence Dt) using
a bounded scalar root-finding (Brent's method).

This module is intentionally decoupled from the full time-marching simulator
so it runs fast — it uses only the initial burning area Ab₀.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.optimize import brentq  # type: ignore

from propellants.base import PropellantProperties
from geometry.base_grain import GrainGeometry
from nozzle.nozzle import NozzleGeometry


@dataclass
class OptimizationResult:
    """Output of a nozzle optimisation run."""
    throat_diameter: float       # Dt  [m]
    throat_area:     float       # At  [m²]
    expansion_ratio: float       # ε   [−]
    predicted_pc:    float       # Pc  [Pa]   at initial Ab
    predicted_thrust: float      # F   [N]    at initial Ab
    klemung_initial:  float      # Kn₀ [−]    at initial Ab


def design_nozzle_from_thrust(
    target_thrust_n: float,
    propellant: PropellantProperties,
    grain: GrainGeometry,
    ambient_pressure_pa: float = 101_325.0,
    expansion_ratio: float = 6.0,
    divergence_half_angle_deg: float = 15.0,
    eta_cstar: float = 0.95,
    eta_cf: float = 0.97,
    dt_min_m: float = 1e-3,    # search lower bound [m]
    dt_max_m: float = 0.20,    # search upper bound [m]
) -> tuple[NozzleGeometry, OptimizationResult]:
    """
    Find the nozzle throat diameter that delivers `target_thrust_n` [N]
    at the initial burning area Ab₀ of the grain.

    Parameters
    ----------
    target_thrust_n          : float — desired average thrust [N]
    propellant               : PropellantProperties
    grain                    : GrainGeometry
    ambient_pressure_pa      : float — Pa [Pa] (default sea level)
    expansion_ratio          : float — ε (default 6.0)
    divergence_half_angle_deg: float — α [°] (default 15°)
    eta_cstar                : float — ηc* (default 0.95)
    eta_cf                   : float — ηCF (default 0.97)
    dt_min_m                 : float — lower bound for Dt search [m]
    dt_max_m                 : float — upper bound for Dt search [m]

    Returns
    -------
    (NozzleGeometry, OptimizationResult)

    Raises
    ------
    ValueError if no solution found in [dt_min_m, dt_max_m].
    """
    Ab0 = grain.initial_state().burning_area
    prop = propellant
    n    = prop.burn_rate_exponent

    def _thrust_for_diameter(Dt: float) -> float:
        """Predict thrust [N] at initial Ab for a given throat diameter."""
        At = math.pi / 4.0 * Dt**2
        Kn = Ab0 / At
        c_star_eff = prop.c_star * eta_cstar
        Pc = (prop.density * prop.burn_rate_coefficient * c_star_eff * Kn) ** (1.0 / (1.0 - n))

        noz_tmp = NozzleGeometry(
            throat_diameter          = Dt,
            expansion_ratio          = expansion_ratio,
            divergence_half_angle_deg= divergence_half_angle_deg,
            eta_cf                   = eta_cf,
        )
        CF = noz_tmp.thrust_coefficient(Pc, ambient_pressure_pa, prop.gamma)
        return CF * Pc * At

    # Residual for root-finding
    def _residual(Dt: float) -> float:
        return _thrust_for_diameter(Dt) - target_thrust_n

    # Validate bracket
    f_lo = _residual(dt_min_m)
    f_hi = _residual(dt_max_m)

    if f_lo * f_hi > 0:
        raise ValueError(
            f"Target thrust {target_thrust_n:.1f} N not achievable with "
            f"Dt in [{dt_min_m*1000:.1f}, {dt_max_m*1000:.1f}] mm.\n"
            f"Thrust at Dt_min = {_thrust_for_diameter(dt_min_m):.1f} N,  "
            f"at Dt_max = {_thrust_for_diameter(dt_max_m):.1f} N.\n"
            "Adjust dt_min_m / dt_max_m bounds or revise target thrust."
        )

    Dt_opt = brentq(_residual, dt_min_m, dt_max_m, xtol=1e-7, maxiter=300)

    nozzle_opt = NozzleGeometry(
        throat_diameter          = Dt_opt,
        expansion_ratio          = expansion_ratio,
        divergence_half_angle_deg= divergence_half_angle_deg,
        eta_cf                   = eta_cf,
    )

    At_opt = nozzle_opt.throat_area
    Kn0    = Ab0 / At_opt
    c_star_eff = prop.c_star * eta_cstar
    Pc_opt = (prop.density * prop.burn_rate_coefficient * c_star_eff * Kn0) ** (1.0 / (1.0 - n))
    CF_opt = nozzle_opt.thrust_coefficient(Pc_opt, ambient_pressure_pa, prop.gamma)
    F_opt  = CF_opt * Pc_opt * At_opt

    opt_result = OptimizationResult(
        throat_diameter  = Dt_opt,
        throat_area      = At_opt,
        expansion_ratio  = expansion_ratio,
        predicted_pc     = Pc_opt,
        predicted_thrust = F_opt,
        klemung_initial  = Kn0,
    )
    return nozzle_opt, opt_result


def design_nozzle_from_pressure(
    target_pressure_pa: float,
    propellant: PropellantProperties,
    grain: GrainGeometry,
    ambient_pressure_pa: float = 101_325.0,
    expansion_ratio: float = 6.0,
    divergence_half_angle_deg: float = 15.0,
    eta_cstar: float = 0.95,
    eta_cf: float = 0.97,
) -> tuple[NozzleGeometry, OptimizationResult]:
    """
    Find the nozzle throat diameter that delivers `target_pressure_pa` [Pa]
    at the initial burning area Ab₀ of the grain.

    Analytical solution from mass balance:
        At = (ρp · a · ηc* · c* · Ab) / Pc^(1-n) / ... 

    Simplifies to closed form:
        At = ρp · a · ηc* · c* · Ab₀ / Pc^(1-n)
    """
    Ab0 = grain.initial_state().burning_area
    prop = propellant
    n    = prop.burn_rate_exponent

    c_star_eff = prop.c_star * eta_cstar
    Pc = target_pressure_pa

    # From equilibrium: Pc^(1-n) = ρp · a · c_star_eff · (Ab/At)
    #  → At = ρp · a · c_star_eff · Ab / Pc^(1-n)
    At_opt = (prop.density * prop.burn_rate_coefficient * c_star_eff * Ab0) / (Pc ** (1.0 - n))
    Dt_opt = math.sqrt(4.0 * At_opt / math.pi)

    nozzle_opt = NozzleGeometry(
        throat_diameter          = Dt_opt,
        expansion_ratio          = expansion_ratio,
        divergence_half_angle_deg= divergence_half_angle_deg,
        eta_cf                   = eta_cf,
    )

    CF_opt = nozzle_opt.thrust_coefficient(Pc, ambient_pressure_pa, prop.gamma)
    F_opt  = CF_opt * Pc * At_opt
    Kn0    = Ab0 / At_opt

    opt_result = OptimizationResult(
        throat_diameter  = Dt_opt,
        throat_area      = At_opt,
        expansion_ratio  = expansion_ratio,
        predicted_pc     = Pc,
        predicted_thrust = F_opt,
        klemung_initial  = Kn0,
    )
    return nozzle_opt, opt_result


def print_optimization_result(
    opt: OptimizationResult,
    mode: str = "thrust",
    target: float = 0.0,
) -> None:  # pragma: no cover
    print("\n  ┌── Nozzle Design Optimization ───────────────────────┐")
    if mode == "thrust":
        print(f"  │  Target thrust:         {target:.1f} N")
    else:
        print(f"  │  Target pressure:       {target/1e6:.4f} MPa")
    print(f"  │  Throat diameter  Dt  = {opt.throat_diameter*1000:.3f} mm")
    print(f"  │  Throat area      At  = {opt.throat_area*1e6:.4f} cm²")
    print(f"  │  Expansion ratio   ε  = {opt.expansion_ratio:.2f}")
    print(f"  │  Predicted Pc         = {opt.predicted_pc/1e6:.4f} MPa")
    print(f"  │  Predicted thrust     = {opt.predicted_thrust:.2f} N")
    print(f"  │  Initial Kn           = {opt.klemung_initial:.1f}")
    print("  └─────────────────────────────────────────────────────┘\n")
