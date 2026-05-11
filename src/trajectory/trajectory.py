"""
Simple 1D trajectory integrator with ISA atmosphere, variable gravity, drag.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np

from src.common.constants import G0, EARTH_RADIUS_M, ISA_T0, ISA_P0, ISA_LAPSE, R_AIR


@dataclass
class TrajectoryResult:
    time: np.ndarray
    altitude: np.ndarray
    velocity: np.ndarray
    acceleration: np.ndarray
    mass: np.ndarray


def isa_density(alt_m: float) -> float:
    """Return air density at altitude alt_m using troposphere ISA (up to 11km)."""
    if alt_m < 0:
        alt_m = 0.0
    T = ISA_T0 - ISA_LAPSE * alt_m
    if T <= 0:
        T = 1.0
    P = ISA_P0 * (T / ISA_T0) ** (G0 / (R_AIR * ISA_LAPSE))
    rho = P / (R_AIR * T)
    return rho


def gravity_at_altitude(alt_m: float) -> float:
    return G0 * (EARTH_RADIUS_M / (EARTH_RADIUS_M + alt_m)) ** 2


def simulate_1d_vertical(
    time_s: np.ndarray,
    thrust_n: np.ndarray,
    mass_flow_kg_s: np.ndarray,
    initial_mass_kg: float,
    dry_mass_kg: float,
    Cd: float,
    area_m2: float,
    dt: float = None,
) -> TrajectoryResult:
    """
    Integrate 1D vertical trajectory using Euler forward.

    Inputs are arrays time_s, thrust_n, mass_flow_kg_s of equal length. initial_mass is
    wet mass at t=0. dry_mass is structural mass after propellant exhausted.
    """
    if dt is None:
        dt_arr = np.diff(time_s, prepend=time_s[0])
    else:
        dt_arr = np.full_like(time_s, dt)
        dt_arr[0] = time_s[0]

    n = len(time_s)
    alt = np.zeros(n, dtype=float)
    vel = np.zeros(n, dtype=float)
    acc = np.zeros(n, dtype=float)
    mass = np.zeros(n, dtype=float)

    m = initial_mass_kg
    for i in range(n):
        t = time_s[i]
        Th = thrust_n[i]
        mdot = mass_flow_kg_s[i]
        rho = isa_density(alt[i-1] if i>0 else 0.0)
        g = gravity_at_altitude(alt[i-1] if i>0 else 0.0)
        D = 0.5 * rho * vel[i-1] ** 2 * Cd * area_m2 if i>0 else 0.0

        # net force: Thrust upward - weight - drag
        Fnet = Th - m * g - D
        a = Fnet / m
        v_new = vel[i-1] + a * dt_arr[i] if i>0 else a * dt_arr[i]
        alt_new = max(0.0, alt[i-1] + v_new * dt_arr[i]) if i>0 else max(0.0, v_new * dt_arr[i])

        mass[i] = max(dry_mass_kg, m - mdot * dt_arr[i])
        acc[i] = a
        vel[i] = v_new
        alt[i] = alt_new
        m = mass[i]

    return TrajectoryResult(time=np.array(time_s), altitude=alt, velocity=vel, acceleration=acc, mass=mass)
