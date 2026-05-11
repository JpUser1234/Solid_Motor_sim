"""
nozzle/nozzle.py
----------------
Converging-diverging nozzle model.

Physical model
--------------
• Isentropic 1-D flow (no friction, no heat loss in nozzle)
• Exit Mach number solved numerically from area-ratio equation (supersonic branch)
• Thrust coefficient CF computed from momentum + pressure terms
• Divergence loss: conical-nozzle factor  λ = (1 + cos α) / 2
• Nozzle efficiency ηCF applied as a global scale on CF

Thrust coefficient formula (ideal, then corrected)
---------------------------------------------------
    CF_mom = λ · √[ 2γ²/(γ−1) · (2/(γ+1))^((γ+1)/(γ−1)) · (1 − (Pe/Pc)^((γ−1)/γ)) ]
    CF_prs = ε · (Pe − Pa) / Pc
    CF     = ηCF · (CF_mom + CF_prs)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from scipy.optimize import brentq   # type: ignore


# ─────────────────────────────────────────────────────────────────────────────
# Nozzle geometry & performance
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NozzleGeometry:
    """
    Converging-diverging nozzle description and performance calculator.

    Parameters
    ----------
    throat_diameter          : Dt [m]
    expansion_ratio          : ε = Ae/At [−]
    divergence_half_angle_deg: α [°] — conical half-angle of diverging section
    convergence_half_angle_deg: θ [°] — convergence half-angle (for reference)
    eta_cf                   : ηCF [−] — nozzle thrust-coefficient efficiency
    """

    throat_diameter: float
    expansion_ratio: float
    divergence_half_angle_deg: float = 15.0
    convergence_half_angle_deg: float = 45.0
    eta_cf: float = 0.97

    # ── Cached Mach solution (init=False: not exposed in constructor) ─────────
    _cached_gamma: float = field(default=-1.0, repr=False, compare=False, init=False)
    _cached_Me: float    = field(default=-1.0, repr=False, compare=False, init=False)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.throat_diameter <= 0:
            raise ValueError(f"throat_diameter must be > 0 (got {self.throat_diameter} m)")
        if self.expansion_ratio < 1.0:
            raise ValueError(f"expansion_ratio must be ≥ 1 (got {self.expansion_ratio})")
        if not (0.0 < self.eta_cf <= 1.0):
            raise ValueError(f"eta_cf must be in (0, 1] (got {self.eta_cf})")
        if not (0.0 < self.divergence_half_angle_deg < 90.0):
            raise ValueError("divergence_half_angle_deg must be in (0°, 90°)")

    # ── Area / diameter helpers ───────────────────────────────────────────────

    @property
    def throat_area(self) -> float:
        """At [m²]"""
        return math.pi / 4.0 * self.throat_diameter**2

    @property
    def exit_area(self) -> float:
        """Ae = ε · At [m²]"""
        return self.throat_area * self.expansion_ratio

    @property
    def exit_diameter(self) -> float:
        """De [m]"""
        return self.throat_diameter * math.sqrt(self.expansion_ratio)

    # ── Divergence loss ───────────────────────────────────────────────────────

    @property
    def lambda_divergence(self) -> float:
        """
        Conical nozzle divergence correction factor.
        λ = (1 + cos α) / 2,   where α is the half-angle of the diverging section.
        A bell nozzle has λ ≈ 0.983 (equivalent ~15°).
        """
        alpha_rad = math.radians(self.divergence_half_angle_deg)
        return (1.0 + math.cos(alpha_rad)) / 2.0

    # ── Isentropic flow relations ─────────────────────────────────────────────

    def exit_mach(self, gamma: float) -> float:
        """
        Supersonic exit Mach number from the area-ratio equation.

        Solved numerically with Brent's method between Me ∈ [1.001, 30].
        """
        if abs(gamma - self._cached_gamma) < 1e-9:
            return self._cached_Me

        def _area_ratio_residual(Me: float) -> float:
            t1 = 2.0 / (gamma + 1.0)
            t2 = 1.0 + (gamma - 1.0) / 2.0 * Me**2
            exp = (gamma + 1.0) / (2.0 * (gamma - 1.0))
            return (1.0 / Me) * (t1 * t2) ** exp - self.expansion_ratio

        if self.expansion_ratio <= 1.0:
            Me = 1.0
        else:
            try:
                Me = brentq(_area_ratio_residual, 1.001, 30.0, xtol=1e-8, maxiter=200)
            except ValueError:
                Me = 1.0  # Fallback: choked at throat
        
        # Cache result
        self._cached_gamma = gamma
        self._cached_Me    = Me
        return Me

    def exit_pressure(self, chamber_pressure_pa: float, gamma: float) -> float:
        """
        Isentropic exit static pressure [Pa].
        Pe = Pc · (1 + (γ−1)/2 · Me²)^(−γ/(γ−1))
        """
        Me = self.exit_mach(gamma)
        exponent = -gamma / (gamma - 1.0)
        return chamber_pressure_pa * (1.0 + (gamma - 1.0) / 2.0 * Me**2) ** exponent

    def exit_velocity(self, chamber_pressure_pa: float, gamma: float,
                      gas_constant: float, flame_temperature: float) -> float:
        """
        Isentropic exit velocity [m/s].
        Ve = Me · √(γ · R · Te)
        """
        Me = self.exit_mach(gamma)
        Pe = self.exit_pressure(chamber_pressure_pa, gamma)
        Te = flame_temperature * (Pe / chamber_pressure_pa) ** ((gamma - 1.0) / gamma)
        return Me * math.sqrt(gamma * gas_constant * Te)

    # ── Thrust coefficient ────────────────────────────────────────────────────

    def thrust_coefficient(
        self,
        chamber_pressure_pa: float,
        ambient_pressure_pa: float,
        gamma: float,
    ) -> float:
        """
        Delivered thrust coefficient CF (including η_CF and λ).

        CF = ηCF · [ λ · CF_momentum + CF_pressure ]

        Parameters
        ----------
        chamber_pressure_pa : Pc [Pa]
        ambient_pressure_pa : Pa [Pa]  (0 for vacuum)
        gamma               : γ [−]
        """
        Pe = self.exit_pressure(chamber_pressure_pa, gamma)
        eps = self.expansion_ratio

        # Momentum term (isentropic 1-D ideal)
        term1 = 2.0 * gamma**2 / (gamma - 1.0)
        term2 = (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (gamma - 1.0))
        pr_ratio = Pe / chamber_pressure_pa
        term3 = 1.0 - pr_ratio ** ((gamma - 1.0) / gamma)
        CF_momentum = self.lambda_divergence * math.sqrt(term1 * term2 * term3)

        # Pressure thrust term
        CF_pressure = eps * (Pe - ambient_pressure_pa) / chamber_pressure_pa

        return self.eta_cf * (CF_momentum + CF_pressure)

    def thrust_coefficient_vacuum(self, chamber_pressure_pa: float, gamma: float) -> float:
        """Vacuum CF (Pa = 0)."""
        return self.thrust_coefficient(chamber_pressure_pa, 0.0, gamma)

    def cf_ideal_vacuum(self, gamma: float) -> float:
        """
        Ideal vacuum CF at a representative pressure (no efficiency factors).
        Useful for design-space comparisons.
        """
        # Use a representative Pc (1 MPa) — CF is nearly independent of Pc for
        # large expansion ratios because Pe/Pc → 0.
        Pc_ref = 1.0e6
        Pe = self.exit_pressure(Pc_ref, gamma)
        term1 = 2.0 * gamma**2 / (gamma - 1.0)
        term2 = (2.0 / (gamma + 1.0)) ** ((gamma + 1.0) / (gamma - 1.0))
        term3 = 1.0 - (Pe / Pc_ref) ** ((gamma - 1.0) / gamma)
        CF_mom = math.sqrt(term1 * term2 * term3)
        CF_prs = self.expansion_ratio * Pe / Pc_ref
        return CF_mom + CF_prs

    # ── Alternate constructor ─────────────────────────────────────────────────

    @classmethod
    def from_throat_diameter(
        cls,
        throat_diameter: float,
        expansion_ratio: float = 4.0,
        divergence_half_angle_deg: float = 15.0,
        eta_cf: float = 0.97,
    ) -> "NozzleGeometry":
        """Convenience constructor — most common use case."""
        return cls(
            throat_diameter=throat_diameter,
            expansion_ratio=expansion_ratio,
            divergence_half_angle_deg=divergence_half_angle_deg,
            eta_cf=eta_cf,
        )

    # ── Display ───────────────────────────────────────────────────────────────

    def summary(self, gamma: float | None = None) -> str:
        lines = [
            "Nozzle Geometry",
            f"  Throat diameter  Dt = {self.throat_diameter*1000:.3f} mm",
            f"  Exit diameter    De = {self.exit_diameter*1000:.3f} mm",
            f"  Throat area      At = {self.throat_area*1e6:.4f} cm2",
            f"  Expansion ratio   eps = {self.expansion_ratio:.3f}",
            f"  Divergence angle  alpha = {self.divergence_half_angle_deg:.1f} deg",
            f"  Divergence factor lambda = {self.lambda_divergence:.4f}",
            f"  Nozzle efficiency eta_CF = {self.eta_cf:.3f}",
        ]
        if gamma is not None:
            Me = self.exit_mach(gamma)
            lines.append(f"  Exit Mach number Me = {Me:.3f}  (gamma = {gamma:.3f})")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.summary()
