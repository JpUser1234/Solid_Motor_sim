"""
propellants/database.py
-----------------------
Built-in propellant database (KNDX, KNSB, KNSU, APCP variants).
Also provides helpers to create custom propellants.

Burn-rate data sources:
  • Richard Nakka — Experimental Rocketry (https://www.nakka-rocketry.net)
  • PROPEP / NASA CEA thermochemical data

Internal storage uses SI units: a [m/s / Pa^n].
User-facing helper `create_custom_propellant` accepts the more
convenient [m/s / MPa^n] and converts automatically.
"""

from typing import Dict
from .base import PropellantProperties

# ─────────────────────────────────────────────────────────────────────────────
# Helper: unit conversion
# ─────────────────────────────────────────────────────────────────────────────

def _a_mpa_to_si(a_mpa: float, n: float) -> float:
    """Convert burn-rate coefficient from MPa-based to Pa-based SI units."""
    return a_mpa / (1.0e6 ** n)


# ─────────────────────────────────────────────────────────────────────────────
# Predefined propellants
# ─────────────────────────────────────────────────────────────────────────────

_DB: Dict[str, PropellantProperties] = {

    # ── Sugar propellants (KNO₃ / fuel) ──────────────────────────────────────

    "KNDX": PropellantProperties(
        name="KNDX — KNO₃/Dextrose 65/35 wt%",
        # r ≈ 9.6 mm/s at 6.895 MPa (1000 psi), n = 0.619  [Nakka]
        burn_rate_coefficient=_a_mpa_to_si(2.903e-3, 0.619),
        burn_rate_exponent=0.619,
        density=1879.0,
        c_star=889.0,
        gamma=1.131,
        molar_mass=41.98,
        flame_temperature=1720.0,
        temperature_sensitivity=2.0e-3,
        reference_temperature=298.15,
    ),

    "KNSB": PropellantProperties(
        name="KNSB — KNO₃/Sorbitol 65/35 wt%",
        # r ≈ 7.9 mm/s at 6.895 MPa, n = 0.688  [Nakka]
        burn_rate_coefficient=_a_mpa_to_si(2.045e-3, 0.688),
        burn_rate_exponent=0.688,
        density=1841.0,
        c_star=908.0,
        gamma=1.136,
        molar_mass=41.30,
        flame_temperature=1784.0,
        temperature_sensitivity=1.5e-3,
        reference_temperature=298.15,
    ),

    "KNSU": PropellantProperties(
        name="KNSU — KNO₃/Sucrose 65/35 wt%",
        # r ≈ 8.0 mm/s at 6.895 MPa, n = 0.600  [Nakka]
        burn_rate_coefficient=_a_mpa_to_si(2.284e-3, 0.600),
        burn_rate_exponent=0.600,
        density=1900.0,
        c_star=876.0,
        gamma=1.133,
        molar_mass=41.70,
        flame_temperature=1694.0,
        temperature_sensitivity=2.0e-3,
        reference_temperature=298.15,
    ),

    # ── APCP variants ─────────────────────────────────────────────────────────

    "APCP_STANDARD": PropellantProperties(
        name="APCP — Standard (AP/HTPB/Al ~68/18/14)",
        # Typical moderate-performance APCP
        burn_rate_coefficient=_a_mpa_to_si(3.517e-3, 0.352),
        burn_rate_exponent=0.352,
        density=1750.0,
        c_star=1578.0,
        gamma=1.21,
        molar_mass=26.0,
        flame_temperature=3300.0,
        temperature_sensitivity=3.0e-3,
        reference_temperature=298.15,
    ),

    "APCP_FAST": PropellantProperties(
        name="APCP — Fast Burn (AP/HTPB/Al ~72/13/15)",
        burn_rate_coefficient=_a_mpa_to_si(6.0e-3, 0.340),
        burn_rate_exponent=0.340,
        density=1770.0,
        c_star=1590.0,
        gamma=1.22,
        molar_mass=25.5,
        flame_temperature=3380.0,
        temperature_sensitivity=3.0e-3,
        reference_temperature=298.15,
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def list_propellants() -> list[str]:
    """Return list of available propellant keys."""
    return list(_DB.keys())


def get_propellant(name: str) -> PropellantProperties:
    """
    Retrieve a built-in propellant by key (case-insensitive).

    Raises
    ------
    KeyError if the propellant is not found.
    """
    key = name.upper()
    if key not in _DB:
        available = ", ".join(_DB.keys())
        raise KeyError(
            f"Propellant '{name}' not found in database.\n"
            f"Available: {available}"
        )
    return _DB[key]


def create_custom_propellant(
    name: str,
    burn_rate_coefficient_mpa: float,
    burn_rate_exponent: float,
    density: float,
    c_star: float,
    gamma: float,
    molar_mass: float,
    flame_temperature: float,
    temperature_sensitivity: float = 0.0,
    reference_temperature: float = 298.15,
) -> PropellantProperties:
    """
    Create a user-defined propellant.

    Parameters (SI unless noted)
    ----------------------------
    name                      : str   — descriptive name
    burn_rate_coefficient_mpa : float — a  [m/s / MPa^n]  ← user-friendly!
    burn_rate_exponent        : float — n  [−]
    density                   : float — ρp [kg/m³]
    c_star                    : float — c* [m/s]
    gamma                     : float — γ  [−]
    molar_mass                : float — M  [g/mol]
    flame_temperature         : float — Tf [K]
    temperature_sensitivity   : float — σp [1/K]  (default 0 → no correction)
    reference_temperature     : float — T_ref [K] (default 298.15 K)

    Returns
    -------
    PropellantProperties with a stored in SI [m/s/Pa^n].

    Example
    -------
    >>> prop = create_custom_propellant(
    ...     name="My APCP",
    ...     burn_rate_coefficient_mpa=4.5e-3,  # 4.5 mm/s at 1 MPa
    ...     burn_rate_exponent=0.38,
    ...     density=1760, c_star=1560, gamma=1.20,
    ...     molar_mass=26.5, flame_temperature=3250,
    ... )
    """
    if not (0.0 < burn_rate_exponent < 1.0):
        raise ValueError(
            f"Burn rate exponent n={burn_rate_exponent} must be in (0, 1) for stable combustion."
        )
    if density <= 0 or c_star <= 0 or flame_temperature <= 0:
        raise ValueError("density, c_star, and flame_temperature must be positive.")

    a_si = _a_mpa_to_si(burn_rate_coefficient_mpa, burn_rate_exponent)
    return PropellantProperties(
        name=name,
        burn_rate_coefficient=a_si,
        burn_rate_exponent=burn_rate_exponent,
        density=density,
        c_star=c_star,
        gamma=gamma,
        molar_mass=molar_mass,
        flame_temperature=flame_temperature,
        temperature_sensitivity=temperature_sensitivity,
        reference_temperature=reference_temperature,
    )


def register_propellant(prop: PropellantProperties, key: str | None = None) -> None:
    """
    Add a propellant to the in-session database so it can be retrieved with
    `get_propellant()`.  Use `key` to override the lookup name; defaults to
    `prop.name.upper()`.
    """
    k = (key or prop.name).upper()
    _DB[k] = prop
