"""
I/O specification dataclasses and design computation following J850_IO_Specification.md
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from src.propellants.base import PropellantProperties
from src.geometry.bates import BatesGrain

# Constants
PA_PER_PSI = 6894.757
INCH_TO_M = 0.0254


@dataclass
class DesignInputs:
    # Required fields FIRST (no defaults)
    DEXT: float                # m — tube outer diameter
    Esp: float                 # m — tube wall thickness
    P1_psi: float              # psi — design chamber pressure
    T1: float                  # K — flame temperature
    ng: int                    # number of BATES segments
    ri: float                  # m — initial internal radius
    Lg: float                  # m — segment length
    Sg: float                  # m — segment separation
    
    # Optional/default tube material properties
    material: str = ""
    E: Optional[float] = None          # Pa — Young's modulus
    sigma_y: Optional[float] = None    # Pa — yield stress

    # Propellant (user-friendly values) — optional if PropellantProperties provided
    a_mpa: Optional[float] = None      # a [m/s / MPa^n] (user units)
    n: Optional[float] = None          # burn rate exponent
    rhoP: Optional[float] = None       # kg/m³ — propellant density

    # Gas thermo (optional, can be taken from PropellantProperties)
    k: Optional[float] = None          # γ — specific heat ratio
    R: Optional[float] = None          # J/kg·K — specific gas constant

    # Nozzle (defaults)
    alpha_deg: float = 12.0            # divergence half-angle
    beta_deg: float = 30.0             # convergence half-angle
    eta_nozzle: float = 0.97           # nozzle efficiency
    Lint_med_mm: float = 3.0           # intermediate section length

    # Bolts (defaults)
    NTornillo: int = 8                 # number of bolts
    DTornillo: float = 0.005           # bolt diameter
    DistT_P: float = 0.012             # bolt center to wall distance

    # Bolt material props (optional)
    Nnucleo: Optional[float] = None    # bolt core diameter
    sigmaY_torn: Optional[float] = None    # bolt yield stress
    tauY_torn: Optional[float] = None      # bolt shear yield
    sigmaU_torn: Optional[float] = None    # bolt ultimate

    # Rocket masses and aerodynamics (defaults)
    mMotor: float = 1.0                # kg
    mFuselaje: float = 1.14            # kg
    mTelemetria: float = 0.10          # kg
    mParacaidas: float = 0.05          # kg
    mPayload: float = 0.52             # kg
    CD: float = 0.40                   # drag coefficient
    Diam_cohete_m: float = 0.0762      # m


@dataclass
class DesignOutputs:
    RINT: float
    re: float
    Vg_unit: float
    mg_unit: float
    LT: float
    L_total: float
    Ap: float
    br: float
    Vp_total: float
    mp_total: float
    TQ: float

    # Isentropic / nozzle
    P1_pa: float
    V1: float
    Vt: float
    Pt: float
    vt: float
    V2: float
    v2: float
    cstar: float
    At: float
    A2: float
    eps: float
    rt_cm: float
    r2_cm: float
    LD_cm: float
    LC_cm: float
    Lnozzle_cm: float

    # Structural quick outputs
    PMAX_est: Optional[float] = None
    sigma_hoop: Optional[float] = None
    sigma_long: Optional[float] = None
    eta_tubo: Optional[float] = None


def compute_design(inputs: DesignInputs, prop: Optional[PropellantProperties] = None, grain: Optional[BatesGrain] = None) -> DesignOutputs:
    """
    Compute design-derived outputs following the spreadsheet logic (J850_IO_Specification.md).
    """
    # Basic geometry
    RINT = (inputs.DEXT - 2.0 * inputs.Esp) / 2.0
    re = RINT - 0.002

    # Grain geometry
    Vg = math.pi * inputs.Lg * (re ** 2 - inputs.ri ** 2)
    mg = (inputs.rhoP or (prop.density if prop else 0.0)) * Vg
    LT = inputs.ng * inputs.Lg
    L_total = (inputs.ng - 1) * inputs.Sg + inputs.ng * inputs.Lg
    Ap = math.pi * inputs.ri ** 2

    # Pressure / burn-rate
    P1_pa = inputs.P1_psi * PA_PER_PSI

    # Compute burn-rate br using prop.burn_rate (SI units)
    if prop is not None:
        br = prop.burn_rate(P1_pa)
    else:
        br = 0.0

    # Total propellant
    Vp_total = Vg * inputs.ng
    rho_p = inputs.rhoP or (prop.density if prop else 0.0)
    mp_total = rho_p * Vp_total

    # Time of burn estimate
    TQ = (re - inputs.ri) / br if br > 0 else 0.0

    # Thermochemical / isentropic (following J850 spec)
    k = inputs.k if inputs.k is not None else (prop.gamma if prop else 1.2)
    Rgas = inputs.R if inputs.R is not None else (prop.gas_constant if prop else 200.0)
    T1 = inputs.T1
    P1 = P1_pa
    Patm = 101325.0

    # Isentropic relations (from J850 module 1.3)
    V1 = Rgas * T1 / P1 if P1 > 0 else 1.0
    Vt = V1 * ((k + 1.0) / 2.0) ** (1.0 / (k - 1.0))
    Pt = P1 * (V1 / Vt) ** k
    Tt = T1 * (V1 / Vt) ** (k - 1.0)
    vt = math.sqrt((2.0 * k / (k + 1.0)) * Rgas * T1)
    
    # Exit state (assuming isentropic expansion to Patm)
    P2 = Patm
    V2 = V1 * (P1 / P2) ** (1.0 / k)
    T2 = T1 * (P2 / P1) ** ((k - 1.0) / k)
    v2 = math.sqrt((2.0 * k / (k - 1.0)) * Rgas * T1 * (1.0 - (P2 / P1) ** ((k - 1.0) / k)))
    
    # c* formula
    cstar = math.sqrt(Rgas * T1 / (k * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0))))

    # Initial burning area
    if grain is not None:
        state0 = grain.initial_state()
        Ab0 = state0.burning_area
    else:
        # approximate: inner cylinder + 2 end faces per segment
        Along0 = math.pi * inputs.ri * 2.0 * inputs.Lg
        Atrans0 = 2.0 * math.pi / 4.0 * (re ** 2 - inputs.ri ** 2)
        Ab0 = Along0 + Atrans0
    
    Ab0_total = Ab0 * inputs.ng
    m_dot = Ab0_total * rho_p * br if rho_p and br else 1.0

    # Nozzle areas (from mass continuity: mdot = rho * V * A = P * A / (R * T * V))
    # At throat: mdot = Pt * At / (cstar_eff)  where cstar_eff ≈ Rgas * T1 * sqrt(2/(k+1))^((k+1)/(k-1)) / sqrt(Rgas * T1)
    # Actually: At = mdot * Vt / vt
    At = (m_dot * Vt / vt) if vt > 0 else 1e-6
    
    # Exit area: A2 = mdot * V2 / v2
    A2 = (m_dot * V2 / v2) if v2 > 0 else At

    # Expansion ratio and nozzle geometry
    eps = A2 / At if At > 0 else 1.0
    
    # Convert to cm for display
    rt_cm = math.sqrt(At * 1e4 / math.pi)
    r2_cm = math.sqrt(A2 * 1e4 / math.pi)
    
    alpha_rad = math.radians(inputs.alpha_deg)
    beta_rad = math.radians(inputs.beta_deg)
    
    tan_alpha = math.tan(alpha_rad) if alpha_rad > 0 else 1.0
    tan_beta = math.tan(beta_rad) if beta_rad > 0 else 1.0
    
    LD_cm = (r2_cm - rt_cm) / tan_alpha if tan_alpha != 0 else 0.1
    h_cm = RINT * 100.0 - rt_cm
    LC_cm = h_cm / tan_beta if tan_beta != 0 else 0.1
    Lnozzle_cm = LD_cm + LC_cm + inputs.Lint_med_mm * 0.1

    # Structural checks
    PMAX_est = P1
    sigma_hoop = PMAX_est * RINT / inputs.Esp if inputs.Esp > 0 else 0.0
    sigma_long = PMAX_est * RINT / (2.0 * inputs.Esp) if inputs.Esp > 0 else 0.0
    eta_tubo = inputs.sigma_y / sigma_hoop if (inputs.sigma_y and sigma_hoop > 0) else None

    return DesignOutputs(
        RINT=RINT, re=re, Vg_unit=Vg, mg_unit=mg, LT=LT, L_total=L_total, Ap=Ap,
        br=br, Vp_total=Vp_total, mp_total=mp_total, TQ=TQ,
        P1_pa=P1, V1=V1, Vt=Vt, Pt=Pt, vt=vt, V2=V2, v2=v2, cstar=cstar,
        At=At, A2=A2, eps=eps, rt_cm=rt_cm, r2_cm=r2_cm, LD_cm=LD_cm, LC_cm=LC_cm, Lnozzle_cm=Lnozzle_cm,
        PMAX_est=PMAX_est, sigma_hoop=sigma_hoop, sigma_long=sigma_long, eta_tubo=eta_tubo,
    )
