"""
main.py — Solid Rocket Motor Simulator entry point.

Usage:
    python main.py               # corre los 3 ejemplos, muestra gráficas
    python main.py --save-only   # guarda a output/ sin mostrar ventanas

Requirements:
    pip install -r requirements.txt
"""

import sys, os, math, matplotlib, matplotlib.pyplot as plt

if "--save-only" in sys.argv or not os.environ.get("DISPLAY", ""):
    matplotlib.use("Agg")

from src.propellants import get_propellant, list_propellants, create_custom_propellant, register_propellant
from src.geometry    import BatesGrain, BatesSegment
from src.nozzle      import NozzleGeometry, design_nozzle_from_thrust, design_nozzle_from_pressure, print_optimization_result
from src.motor       import SolidMotorSimulator, MotorConfig
from src.plots       import plot_full_dashboard, save_all_plots
from src.structure.analysis import thin_walled_vessel, simple_bolt_analysis
from src.trajectory.trajectory import simulate_1d_vertical
import numpy as _np
from src.io.spec import DesignInputs, compute_design
from src.propellants.base import PropellantProperties
from src.geometry.bates import BatesGrain

SHOW = "--save-only" not in sys.argv

def _run(config, name, tag):
    sim    = SolidMotorSimulator(config)
    result = sim.run()
    sim.print_summary(result)
    save_all_plots(result, tag, "output",
                   config.eta_cstar, config.nozzle.eta_cf, config.nozzle.lambda_divergence)
    if SHOW:
        fig = plot_full_dashboard(result, name, config.eta_cstar,
                                  config.nozzle.eta_cf, config.nozzle.lambda_divergence)
        plt.show()
    
    # --- Structural quick-check ------------------------------------------------
    try:
        # --- Design I/O outputs (J850 spec) ------------------------------------
        try:
            di = DesignInputs(
                DEXT=config.grain.get_outer_diameter() + 2.0 * config.casing_thickness_m,
                Esp=config.casing_thickness_m,
                material="",
                E=None,
                sigma_y=config.casing_yield_pa,
                P1_psi=float(result.max_chamber_pressure / 6894.757) if result.max_chamber_pressure>0 else 0.0,
                T1=config.initial_temperature_k or config.propellant.flame_temperature,
                ng=config.grain.n_segments,
                ri=config.grain._segments[0].inner_diameter,
                Lg=config.grain._segments[0].length,
                Sg=0.0,
                a_mpa=None,
                n=config.propellant.burn_rate_exponent,
                rhoP=config.propellant.density,
                k=config.propellant.gamma,
                R=config.propellant.gas_constant,
                alpha_deg=config.nozzle.divergence_half_angle_deg,
                beta_deg=config.nozzle.convergence_half_angle_deg,
                eta_nozzle=config.nozzle.eta_cf,
                NTornillo=config.n_bolts,
                DTornillo=config.bolt_shank_area_m2 ** 0.5 if config.bolt_shank_area_m2>0 else 0.005,
                DistT_P=config.bolt_bearing_area_m2 ** 0.5 if config.bolt_bearing_area_m2>0 else 0.012,
                Nnucleo=None,
                sigmaY_torn=config.bolt_shear_strength_pa,
                sigmaU_torn=None,
                mMotor=config.vehicle_dry_mass_kg,
                CD=config.drag_coefficient,
            )
            design_out = compute_design(di, config.propellant, config.grain)
            print("\n  Design Outputs:")
            print(f"    RINT = {design_out.RINT:.4f} m, re = {design_out.re:.4f} m, TQ = {design_out.TQ:.3f} s")
            print(f"    mp_total = {design_out.mp_total:.3f} kg, At = {design_out.At:.6e} m2, eps = {design_out.eps:.3f}")
        except Exception as _de:
            print("  Design outputs computation skipped (error):", _de)

        # use grain outer diameter as casing internal diameter
        D = config.grain.get_outer_diameter()
        r_inner = D / 2.0
        wall = config.casing_thickness_m
        struct = thin_walled_vessel(result.max_chamber_pressure, r_inner, wall, config.casing_yield_pa)
        print("\n  Structural Check:")
        print(f"    Hoop stress = {struct.hoop_stress_pa/1e6:.2f} MPa, SF = {struct.safety_factor_hoop:.2f}")
        print(f"    Long. stress = {struct.longitudinal_stress_pa/1e6:.2f} MPa, SF = {struct.safety_factor_long:.2f}")

        # simple bolt analysis using axial force ~ pressure * area
        area_cylinder = math.pi * D * (D/2.0)  # crude: lateral area ~ π D r
        axial_force = result.max_chamber_pressure * math.pi * (r_inner ** 2)
        bolts = simple_bolt_analysis(axial_force, config.n_bolts, config.bolt_shear_strength_pa, config.bolt_shank_area_m2, config.bolt_bearing_area_m2)
        print(f"    Bolt shear per bolt = {bolts.shear_per_bolt_n:.1f} N, bearing stress = {bolts.bearing_stress_pa/1e6:.2f} MPa")
    except Exception as _e:
        print("  Structural check skipped (error):", _e)

    # --- Trajectory 1D integration ------------------------------------------------
    try:
        t = result.time
        thrust = result.thrust
        mflow = result.mass_flow
        initial_mass = result.initial_propellant_mass + config.vehicle_dry_mass_kg
        dry = config.vehicle_dry_mass_kg
        traj = simulate_1d_vertical(t, thrust, mflow, initial_mass, dry, config.drag_coefficient, config.frontal_area_m2)

        # Save trajectory
        out_path = os.path.join("output", f"trajectory_{tag}.csv")
        _np.savetxt(out_path, _np.column_stack([traj.time, traj.altitude, traj.velocity, traj.acceleration, traj.mass]),
                    header="t[s],alt[m],vel[m/s],acc[m/s2],mass[kg]", delimiter=",")
        print(f"  Trajectory saved to {out_path}")
    except Exception as _e:
        print("  Trajectory simulation skipped (error):", _e)

    return result

"""
# ─────────────────────────────────────────────────────────────────────────────
# Ejemplo 1 — KNDX + BATES ×4 (dimensiones → impulso)
# ─────────────────────────────────────────────────────────────────────────────
def ejemplo_1():
    print("\n" + "═"*60)
    print("  EJEMPLO 1 — KNDX / BATES ×4 | dimenciones → impulso")
    print("═"*60)
    prop   = get_propellant("KNDX")
    grain  = BatesGrain.uniform(4, 0.075, 0.030, 0.120, inhibited_ends=False)
    nozzle = NozzleGeometry(0.017, 6.0, 15.0, eta_cf=0.97)
    config = MotorConfig(prop, grain, nozzle, eta_cstar=0.95,
                         ambient_pressure_pa=101_325.0, dt=0.002)
    print(prop); print(); print(grain.summary()); print(nozzle.summary(prop.gamma))
    _run(config, "KNDX / BATES ×4", "KNDX_BATES4")


# ─────────────────────────────────────────────────────────────────────────────
# Ejemplo 2 — Propelente custom + optimizador de tobera → target thrust
# ─────────────────────────────────────────────────────────────────────────────
def ejemplo_2():
    print("\n" + "═"*60)
    print("  EJEMPLO 2 — APCP Custom + Optimizador de Tobera (350 N)")
    print("═"*60)
    prop = create_custom_propellant(
        name="Mi APCP (AP/HTPB/Al)",
        burn_rate_coefficient_mpa=3.8e-3, burn_rate_exponent=0.380,
        density=1755, c_star=1560, gamma=1.20, molar_mass=26.2,
        flame_temperature=3280, temperature_sensitivity=2.5e-3,
    )
    register_propellant(prop, "MI_APCP")
    grain  = BatesGrain.uniform(3, 0.054, 0.022, 0.140)
    print(prop); print(); print(grain.summary())

    nozzle, opt = design_nozzle_from_thrust(350.0, prop, grain, expansion_ratio=6.0,
                                            eta_cstar=0.94, eta_cf=0.97)
    print_optimization_result(opt, "thrust", 350.0)
    print(nozzle.summary(prop.gamma))
    config = MotorConfig(prop, grain, nozzle, eta_cstar=0.94, dt=0.001)
    _run(config, "Custom APCP / BATES ×3 (optimizado)", "CustomAPCP_BATES3")



# ─────────────────────────────────────────────────────────────────────────────
# Ejemplo 3 — Segmentos de port mixto → perfil progresivo de empuje
# ─────────────────────────────────────────────────────────────────────────────
def ejemplo_3():
    print("\n" + "═"*60)
    print("  EJEMPLO 3 — KNSB / BATES ×3 con puertos mixtos")
    print("═"*60)
    prop  = get_propellant("KNSB")
    grain = BatesGrain([
        BatesSegment(0.060, 0.020, 0.100),   # port chico  → regresivo
        BatesSegment(0.060, 0.025, 0.100),   # port medio
        BatesSegment(0.060, 0.030, 0.100),   # port grande → progresivo
    ])
    nozzle = NozzleGeometry(0.013, 5.0, 15.0, eta_cf=0.97)
    config = MotorConfig(prop, grain, nozzle, eta_cstar=0.95, dt=0.001)
    print(prop); print(); print(grain.summary()); print(nozzle.summary(prop.gamma))
    _run(config, "KNSB / BATES ×3 (ports mixtos)", "KNSB_Mixed3")

"""

# ─────────────────────────────────────────────────────────────────────────────
# Prueba 1 — Motor J
# ─────────────────────────────────────────────────────────────────────────────
def Motor_J():
    print("\n" + "═"*60)
    print(" Motor J — KNSU + Optimizador de Tobera (800 N)")
    print("═"*60)
    prop = get_propellant("KNSU")
    grain  = BatesGrain.uniform(4, 0.052, 0.017, 0.125)
    print(prop); print(); print(grain.summary())

    nozzle, opt = design_nozzle_from_thrust(800.0, prop, grain, expansion_ratio=6.0,
                                            eta_cstar=0.94, eta_cf=0.96)
    print_optimization_result(opt, "thrust", 800.0)
    print(nozzle.summary(prop.gamma))
    config = MotorConfig(prop, grain, nozzle, eta_cstar=0.94, dt=0.001)
    _run(config, "KNSU / BATES ×4 (optimizado)", "KNSU_BATES4")


# ─────────────────────────────────────────────────────────────────────────────
# Prueba 2 — Motor J
# ─────────────────────────────────────────────────────────────────────────────
def Prueba_2():
    print("\n" + "═"*60)
    print("  Prueba 2 — KNSU / BATES ×4 | dimenciones → impulso")
    print("═"*60)
    prop   = get_propellant("KNSU")
    grain  = BatesGrain.uniform(4, 0.0451, 0.01, 0.07, inhibited_ends=False)
    nozzle = NozzleGeometry(0.01162, 12.63, 12, 30, eta_cf=0.97)
    config = MotorConfig(prop, grain, nozzle, eta_cstar=0.95,
                         ambient_pressure_pa=101_325.0,initial_temperature_k=1720 ,dt=0.002)
    print(prop); print(); print(grain.summary()); print(nozzle.summary(prop.gamma))
    _run(config, "KNSU / BATES ×4", "KNSU_BATES4")

def run_j850_test():
    # --- User inputs (from the prompt) ---------------------------------
    DEXT = 0.0521
    Esp = 0.0016
    sigma_Y = 275e6
    tau_U = 205e6
    sigma_U = 310e6
    E_mod = 69e9

    P1_psi = 1000.0
    T1 = 1720.0

    ng = 4
    ri = 0.010
    Lg = 0.070
    Sg = 0.002

    a_psi_units = 0.0665   # inches/s per psi^n (spreadsheet units)
    n = 0.319
    rhoP = 1776.25

    k = 1.044
    Rgas = 195.71

    alpha = 12.0
    beta = 30.0
    eta_nozzle = 0.85
    Lint_med = 3.0

    N_torn = 8
    D_torn = 0.005
    DistTP = 0.012
    N_nucleo = 0.0038
    sigmaY_torn = 250e6
    tauY_torn = 145e6
    sigmaU_torn = 400e6

    H_inic = 100.0
    lat = 9.936111
    CD = 0.40
    m_motor = 1.00
    m_fuselaje = 1.14
    m_telemetria = 0.10
    m_paracaidas = 0.05
    m_payload = 0.52

    # --- Prepare propellant object (convert burn-rate to SI) ---------
    # a_psi_units [in/s / psi^n] -> a_si [m/s / Pa^n]
    in_to_m = 0.0254
    pa_per_psi = 6894.757
    a_m_per_s = a_psi_units * in_to_m
    a_si = a_m_per_s / (pa_per_psi ** n)

    molar_mass = 8314.46 / Rgas
    # compute c* from formula used in compute_design for consistency
    cstar_calc = math.sqrt(Rgas * T1 / (k * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0))))

    prop = PropellantProperties(
        name="J850_CUSTOM",
        burn_rate_coefficient=a_si,
        burn_rate_exponent=n,
        density=rhoP,
        c_star=cstar_calc,
        gamma=k,
        molar_mass=molar_mass,
        flame_temperature=T1,
    )

    # --- Grain and design --------------------------------------------
    D_inner = DEXT - 2.0 * Esp
    grain = BatesGrain.uniform(ng, D_inner, ri, Lg)

    di = DesignInputs(
        DEXT=DEXT,
        Esp=Esp,
        material="Aluminio 6061-T6",
        E=E_mod,
        sigma_y=sigma_Y,
        P1_psi=P1_psi,
        T1=T1,
        ng=ng,
        ri=ri,
        Lg=Lg,
        Sg=Sg,
        a_mpa=None,
        n=n,
        rhoP=rhoP,
        k=k,
        R=Rgas,
        alpha_deg=alpha,
        beta_deg=beta,
        eta_nozzle=eta_nozzle,
        Lint_med_mm=Lint_med,
        NTornillo=N_torn,
        DTornillo=D_torn,
        DistT_P=DistTP,
        Nnucleo=N_nucleo,
        sigmaY_torn=sigmaY_torn,
    )

    design_out = compute_design(di, prop, grain)
    print("\n--- J850 Test: Design outputs ---")
    print(f"br (computed) = {design_out.br:.5f} m/s")
    print(f"TQ = {design_out.TQ:.4f} s, At = {design_out.At:.6e} m², A2 = {design_out.A2:.6e} m², eps = {design_out.eps:.3f}")
    if design_out.v2 > 0:
        T_exit = T1 * ((design_out.v2 / (2.0 * k / (k - 1.0) * Rgas * T1)) if design_out.v2 > 0 else 1.0)
        a_exit = math.sqrt(k * Rgas * max(1.0, T_exit))
        M2_approx = design_out.v2 / a_exit if a_exit > 0 else 1.0
        print(f"M2 (approx) = {M2_approx:.3f}")
    print(f"c* = {design_out.cstar:.3f} m/s, v2 = {design_out.v2:.3f} m/s")

    # --- Build nozzle from At/A2 ------------------------------------
    target_peak_pressure_pa = 7.0e6
    At_seed = design_out.At if design_out.At > 0.0 else 1e-6
    eps = design_out.eps if design_out.eps > 0.0 else 6.0

    def _run_with_area(area_m2: float):
        throat_diameter = math.sqrt(4.0 * area_m2 / math.pi)
        nozzle_candidate = NozzleGeometry(
            throat_diameter=throat_diameter,
            expansion_ratio=eps,
            divergence_half_angle_deg=alpha,
            eta_cf=eta_nozzle,
        )
        sim_candidate = SolidMotorSimulator(MotorConfig(prop, grain, nozzle_candidate, eta_cstar=0.94, ambient_pressure_pa=101325.0, dt=0.001))
        return sim_candidate.run()

    At_used = At_seed
    try:
        baseline_result = _run_with_area(At_seed)
        pressure_factor = max(baseline_result.max_chamber_pressure, 1.0) / target_peak_pressure_pa
        At_calibrated = At_seed * pressure_factor ** (1.0 - n)
        At_calibrated = max(At_calibrated, 1e-6)
        nozzle = NozzleGeometry(
            throat_diameter=math.sqrt(4.0 * At_calibrated / math.pi),
            expansion_ratio=eps,
            divergence_half_angle_deg=alpha,
            eta_cf=eta_nozzle,
        )
        At_used = nozzle.throat_area
        print(f"  Calibrated throat area for ~7 MPa peak: {At_calibrated:.6e} m2")
    except Exception as _cal_err:
        print("  Pressure calibration skipped (error):", _cal_err)
        At_calibrated = At_seed
        throat_diameter = math.sqrt(4.0 * At_calibrated / math.pi)
        nozzle = NozzleGeometry(throat_diameter=throat_diameter, expansion_ratio=eps, divergence_half_angle_deg=alpha, eta_cf=eta_nozzle)
        At_used = nozzle.throat_area

    # --- Motor config and run simulation -----------------------------
    cfg = MotorConfig(prop, grain, nozzle, eta_cstar=0.94, ambient_pressure_pa=101325.0, dt=0.001)
    print("\nRunning quasi-steady simulation...")
    result = _run(cfg, "J850 Test", "J850_TEST")

    # --- Print summary comparisons ----------------------------------
    print("\n--- Comparison with expected (spreadsheet) ---")
    print(f"Expected br ~ 0.01530 m/s  | Computed br = {design_out.br:.5f} m/s")
    print(f"Expected TQ ~ 0.8138 s     | Computed TQ = {design_out.TQ:.4f} s")
    print(f"Expected At ~ 1.059e-4 m2  | Computed At = {design_out.At:.6e} m2")
    print(f"Expected A2 ~ 1.337e-3 m2  | Computed A2 = {design_out.A2:.6e} m2")
    print(f"Expected c* ~ 941.3 m/s    | Computed c* = {design_out.cstar:.3f} m/s")
    print(f"Calibrated nozzle At used in sim = {At_used:.6e} m2")
    print(f"Simulated peak chamber pressure  = {result.max_chamber_pressure/1e6:.3f} MPa")
    print(f"Simulation IT_esp = {result.total_impulse:.1f} N.s, Isp = {result.specific_impulse_sl:.1f} s")

    # Note: trajectory outputs saved to output/trajectory_J850_TEST.csv


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"  Propelentes disponibles: {list_propellants()}")
    # Run J850 test case as requested

    run_j850_test()
    print("\n  * J850 test completed. Revisa output/ para archivos generados.\n")
