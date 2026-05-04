"""
motor/simulation.py
-------------------
Quasi-steady 0-D solid rocket motor simulator.

Physical model
--------------
At each time step the simulator:

  1. Queries the grain for current burning surface area Ab and remaining volume.
  2. Computes quasi-steady equilibrium chamber pressure from mass balance:

         ṁ_gen  = ρp · Ab · r(Pc)
         ṁ_out  = Pc · At / (ηc* · c*)

     Setting ṁ_gen = ṁ_out and solving for Pc:

         Pc = ( ρp · a · ηc* · c* · Kn )^(1/(1-n))

     where Kn = Ab / At  (Klemmung / K-value).

  3. Evaluates burn rate  r = a · Pc^n  (with optional temperature correction).
  4. Computes thrust:   F = ηCF · CF(Pc, Pa, γ) · Pc · At
  5. Advances web:      web_burned += r · dt

Stability note
--------------
For stable combustion, the exponent n must satisfy 0 < n < 1.  The simulator
will raise a warning if this condition is not met, as the equilibrium may be
numerically unstable.
"""

from __future__ import annotations

import warnings
import math
from dataclasses import dataclass, field
from typing import List

import numpy as np

from propellants.base import PropellantProperties
from geometry.base_grain import GrainGeometry
from nozzle.nozzle import NozzleGeometry

_G0 = 9.80665   # standard gravity [m/s²]


# ─────────────────────────────────────────────────────────────────────────────
# Result container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SimulationResult:
    """
    Complete time-history and integrated performance of one motor simulation.
    """

    # ── Time-history arrays ───────────────────────────────────────────────────
    time:               np.ndarray   # t   [s]
    chamber_pressure:   np.ndarray   # Pc  [Pa]
    thrust:             np.ndarray   # F   [N]    (at ambient pressure)
    thrust_vacuum:      np.ndarray   # Fv  [N]    (vacuum)
    mass_flow:          np.ndarray   # ṁ   [kg/s]
    burn_rate:          np.ndarray   # r   [m/s]
    burning_area:       np.ndarray   # Ab  [m²]
    web_burned:         np.ndarray   # Δw  [m]    (cumulative)
    klemung:            np.ndarray   # Kn  [−]
    propellant_mass:    np.ndarray   # mp  [kg]   (remaining)
    exit_pressure:      np.ndarray   # Pe  [Pa]
    thrust_coefficient: np.ndarray   # CF  [−]    (at ambient)
    thrust_coeff_vac:   np.ndarray   # CFv [−]    (vacuum)

    # ── Scalar performance metrics ────────────────────────────────────────────
    total_impulse:          float = 0.0   # It   [N·s]
    total_impulse_vacuum:   float = 0.0   # It_v [N·s]
    specific_impulse_sl:    float = 0.0   # Isp  [s]  at sea level
    specific_impulse_vac:   float = 0.0   # Isp  [s]  vacuum
    max_thrust:             float = 0.0   # [N]
    avg_thrust:             float = 0.0   # [N]
    burn_time:              float = 0.0   # tb   [s]
    max_chamber_pressure:   float = 0.0   # [Pa]
    avg_chamber_pressure:   float = 0.0   # [Pa]
    max_klemung:            float = 0.0   # Kn_max [−]
    initial_propellant_mass: float = 0.0  # mp0  [kg]
    propellant_consumed:    float = 0.0   # Δmp  [kg]
    propellant_burnout_frac: float = 0.0  # Δmp/mp0 [−]
    eta_delivered:          float = 0.0   # ηdeliv = ηc* · ηCF · λ


# ─────────────────────────────────────────────────────────────────────────────
# Motor configuration
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MotorConfig:
    """
    All inputs needed to define and simulate a solid rocket motor.
    """

    propellant: PropellantProperties
    grain: GrainGeometry
    nozzle: NozzleGeometry

    # ── Efficiency factors ────────────────────────────────────────────────────
    eta_cstar: float = 0.95            # ηc* — combustion efficiency [−]

    # ── Atmospheric / thermal conditions ─────────────────────────────────────
    ambient_pressure_pa: float = 101_325.0    # Pa  (sea level)
    initial_temperature_k: float = 298.15     # K   (room temperature)

    # ── Simulation control ────────────────────────────────────────────────────
    dt: float = 0.002                         # time step [s]
    max_burn_time: float = 120.0              # [s]  hard upper limit
    pressure_threshold_pa: float = 0.5e5     # minimum Pc to continue [Pa]


# ─────────────────────────────────────────────────────────────────────────────
# Simulator
# ─────────────────────────────────────────────────────────────────────────────

class SolidMotorSimulator:
    """
    Quasi-steady 0-D simulator for a solid rocket motor.

    Usage
    -----
    >>> cfg = MotorConfig(propellant=..., grain=..., nozzle=...)
    >>> sim = SolidMotorSimulator(cfg)
    >>> result = sim.run()
    >>> sim.print_summary(result)
    """

    def __init__(self, config: MotorConfig) -> None:
        self.cfg = config
        self._validate()

    def _validate(self) -> None:
        n = self.cfg.propellant.burn_rate_exponent
        if not (0.0 < n < 1.0):
            warnings.warn(
                f"Burn-rate exponent n={n:.3f} is outside (0, 1). "
                "Combustion may be unstable.",
                UserWarning, stacklevel=2,
            )
        if not (0.0 < self.cfg.eta_cstar <= 1.0):
            raise ValueError(f"eta_cstar must be in (0, 1], got {self.cfg.eta_cstar}")

    # ── Core quasi-steady pressure solver ────────────────────────────────────

    def _equilibrium_pressure(self, Ab: float) -> float:
        """
        Quasi-steady chamber pressure [Pa] from mass balance.

            Pc = (ρp · a · ηc* · c* · Kn)^(1/(1−n))
        """
        prop = self.cfg.propellant
        At = self.cfg.nozzle.throat_area
        Kn = Ab / At

        c_star_eff = prop.c_star * self.cfg.eta_cstar
        base = prop.density * prop.burn_rate_coefficient * c_star_eff * Kn
        exponent = 1.0 / (1.0 - prop.burn_rate_exponent)
        return base ** exponent

    # ── Main simulation loop ──────────────────────────────────────────────────

    def run(self) -> SimulationResult:
        """
        Execute the quasi-steady simulation.

        Returns
        -------
        SimulationResult with full time-history and scalar metrics.
        """
        cfg = self.cfg
        prop = cfg.propellant
        nozzle = cfg.nozzle
        grain = cfg.grain

        At = nozzle.throat_area
        m0 = grain.total_propellant_mass(prop.density)
        T_init = cfg.initial_temperature_k
        Pa = cfg.ambient_pressure_pa

        # ── Pre-allocate result lists ─────────────────────────────────────────
        times: List[float] = []
        pressures: List[float] = []
        thrusts: List[float] = []
        thrusts_vac: List[float] = []
        mass_flows: List[float] = []
        burn_rates: List[float] = []
        burning_areas: List[float] = []
        web_hist: List[float] = []
        kn_hist: List[float] = []
        prop_masses: List[float] = []
        exit_pressures: List[float] = []
        cf_hist: List[float] = []
        cf_vac_hist: List[float] = []

        # ── Simulation loop ───────────────────────────────────────────────────
        web_burned = 0.0
        t = 0.0
        step = 0

        while t <= cfg.max_burn_time:
            state = grain.regress(web_burned)

            if state.is_burned_out or state.burning_area < 1.0e-12:
                break

            Ab = state.burning_area
            Pc = self._equilibrium_pressure(Ab)

            if Pc < cfg.pressure_threshold_pa:
                break

            r = prop.burn_rate(Pc, T_init)
            m_dot = prop.density * Ab * r   # total mass flow [kg/s]

            # ── Nozzle performance ────────────────────────────────────────────
            CF_sl  = nozzle.thrust_coefficient(Pc, Pa, prop.gamma)
            CF_vac = nozzle.thrust_coefficient_vacuum(Pc, prop.gamma)
            F_sl   = CF_sl  * Pc * At
            F_vac  = CF_vac * Pc * At
            Pe     = nozzle.exit_pressure(Pc, prop.gamma)
            Kn     = Ab / At

            # ── Store ─────────────────────────────────────────────────────────
            times.append(t)
            pressures.append(Pc)
            thrusts.append(F_sl)
            thrusts_vac.append(F_vac)
            mass_flows.append(m_dot)
            burn_rates.append(r)
            burning_areas.append(Ab)
            web_hist.append(web_burned)
            kn_hist.append(Kn)
            prop_masses.append(prop.density * state.volume)
            exit_pressures.append(Pe)
            cf_hist.append(CF_sl)
            cf_vac_hist.append(CF_vac)

            # ── Advance state ─────────────────────────────────────────────────
            web_burned += r * cfg.dt
            t          += cfg.dt
            step       += 1

        if len(times) < 2:
            raise RuntimeError(
                "Simulation ended immediately (< 2 time steps). "
                "Check grain dimensions, nozzle throat area, and propellant data."
            )

        # ── Convert to NumPy arrays ───────────────────────────────────────────
        t_arr   = np.array(times, dtype=float)
        F_arr   = np.array(thrusts, dtype=float)
        Fv_arr  = np.array(thrusts_vac, dtype=float)
        Pc_arr  = np.array(pressures, dtype=float)
        m_arr   = np.array(mass_flows, dtype=float)

        # ── Integrate performance metrics ─────────────────────────────────────
        _trapz = getattr(np, "trapezoid", None) or np.trapz   # compat NumPy <2 / >=2
        It_sl  = float(_trapz(F_arr,  t_arr))
        It_vac = float(_trapz(Fv_arr, t_arr))

        mp_consumed = float(_trapz(m_arr, t_arr))   # [kg]

        burn_time = float(t_arr[-1] - t_arr[0])
        avg_thrust = It_sl / burn_time if burn_time > 0.0 else 0.0

        Isp_sl  = It_sl  / (mp_consumed * _G0) if mp_consumed > 0.0 else 0.0
        Isp_vac = It_vac / (mp_consumed * _G0) if mp_consumed > 0.0 else 0.0

        eta_delivered = cfg.eta_cstar * nozzle.eta_cf * nozzle.lambda_divergence

        return SimulationResult(
            # Time-history
            time               = t_arr,
            chamber_pressure   = Pc_arr,
            thrust             = F_arr,
            thrust_vacuum      = Fv_arr,
            mass_flow          = m_arr,
            burn_rate          = np.array(burn_rates,    dtype=float),
            burning_area       = np.array(burning_areas, dtype=float),
            web_burned         = np.array(web_hist,      dtype=float),
            klemung            = np.array(kn_hist,       dtype=float),
            propellant_mass    = np.array(prop_masses,   dtype=float),
            exit_pressure      = np.array(exit_pressures,dtype=float),
            thrust_coefficient = np.array(cf_hist,       dtype=float),
            thrust_coeff_vac   = np.array(cf_vac_hist,   dtype=float),
            # Scalars
            total_impulse           = It_sl,
            total_impulse_vacuum    = It_vac,
            specific_impulse_sl     = Isp_sl,
            specific_impulse_vac    = Isp_vac,
            max_thrust              = float(np.max(F_arr)),
            avg_thrust              = avg_thrust,
            burn_time               = burn_time,
            max_chamber_pressure    = float(np.max(Pc_arr)),
            avg_chamber_pressure    = float(np.mean(Pc_arr)),
            max_klemung             = float(np.max(np.array(kn_hist))),
            initial_propellant_mass = m0,
            propellant_consumed     = mp_consumed,
            propellant_burnout_frac = mp_consumed / m0 if m0 > 0.0 else 0.0,
            eta_delivered           = eta_delivered,
        )

    # ── Summary printer ───────────────────────────────────────────────────────

    def print_summary(self, result: SimulationResult) -> None:  # pragma: no cover
        """Print a formatted performance summary to stdout."""
        cfg    = self.cfg
        prop   = cfg.propellant
        nozzle = cfg.nozzle
        grain  = cfg.grain

        W = 58
        sep = "═" * W

        print(f"\n{sep}")
        print(f"{'  SOLID MOTOR SIMULATION — PERFORMANCE SUMMARY':^{W}}")
        print(sep)

        print(f"\n  {'PROPELLANT':}")
        print(f"    {prop.name}")
        print(f"    c* (theoretical)  = {prop.c_star:.1f} m/s")
        print(f"    c* (effective)    = {prop.c_star*cfg.eta_cstar:.1f} m/s  (ηc* = {cfg.eta_cstar:.3f})")
        print(f"    Tf  = {prop.flame_temperature:.0f} K     γ = {prop.gamma:.4f}")

        print(f"\n  {'GRAIN':}")
        print(f"    {grain!r}")
        print(f"    Initial propellant mass = {result.initial_propellant_mass*1000:.2f} g")

        print(f"\n  {'NOZZLE':}")
        print(f"    Dt = {nozzle.throat_diameter*1000:.3f} mm   "
              f"De = {nozzle.exit_diameter*1000:.3f} mm   "
              f"ε = {nozzle.expansion_ratio:.3f}")
        print(f"    α = {nozzle.divergence_half_angle_deg:.1f}°   "
              f"λ = {nozzle.lambda_divergence:.4f}   "
              f"ηCF = {nozzle.eta_cf:.3f}")

        print(f"\n  {'PERFORMANCE':}")
        print(f"    Total impulse   (SL)  It  = {result.total_impulse:.2f} N·s")
        print(f"    Total impulse   (vac) It  = {result.total_impulse_vacuum:.2f} N·s")
        print(f"    Specific impulse(SL)  Isp = {result.specific_impulse_sl:.1f} s")
        print(f"    Specific impulse(vac) Isp = {result.specific_impulse_vac:.1f} s")
        print(f"    Max thrust      Fmax = {result.max_thrust:.2f} N")
        print(f"    Avg thrust      Favg = {result.avg_thrust:.2f} N")
        print(f"    Burn time       tb   = {result.burn_time:.3f} s")

        print(f"\n  {'CHAMBER / BURN':}")
        print(f"    Max  Pc = {result.max_chamber_pressure/1e6:.4f} MPa")
        print(f"    Avg  Pc = {result.avg_chamber_pressure/1e6:.4f} MPa")
        print(f"    Max  Kn = {result.max_klemung:.1f}")

        print(f"\n  {'EFFICIENCY':}")
        print(f"    ηc*  (combustion)  = {cfg.eta_cstar*100:.1f}%")
        print(f"    ηCF  (nozzle)      = {nozzle.eta_cf*100:.1f}%")
        print(f"    λ    (divergence)  = {nozzle.lambda_divergence*100:.2f}%")
        print(f"    η    (delivered)   = {result.eta_delivered*100:.2f}%")
        print(f"    Propellant used    = {result.propellant_burnout_frac*100:.1f}%  "
              f"({result.propellant_consumed*1000:.2f} g)")

        print(f"\n{sep}\n")
