"""
main.py — Solid Rocket Motor Simulator entry point.

Usage:
    python main.py               # corre los 3 ejemplos, muestra gráficas
    python main.py --save-only   # guarda a output/ sin mostrar ventanas

Requirements:
    pip install -r requirements.txt
"""

import sys, os, matplotlib, matplotlib.pyplot as plt

if "--save-only" in sys.argv or not os.environ.get("DISPLAY", ""):
    matplotlib.use("Agg")

from src.propellants import get_propellant, list_propellants, create_custom_propellant, register_propellant
from src.geometry    import BatesGrain, BatesSegment
from src.nozzle      import NozzleGeometry, design_nozzle_from_thrust, design_nozzle_from_pressure, print_optimization_result
from src.motor       import SolidMotorSimulator, MotorConfig
from src.plots       import plot_full_dashboard, save_all_plots

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
    grain  = BatesGrain.uniform(4, 0.075, 0.030, 0.120, inhibited_ends=False)
    nozzle = NozzleGeometry(0.017, 6.0, 15.0, eta_cf=0.97)
    config = MotorConfig(prop, grain, nozzle, eta_cstar=0.95,
                         ambient_pressure_pa=101_325.0,initial_temperature_k=1720 ,dt=0.002)
    print(prop); print(); print(grain.summary()); print(nozzle.summary(prop.gamma))
    _run(config, "KNSU / BATES ×4", "KNSU_BATES4")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"  Propelentes disponibles: {list_propellants()}")
    Motor_J()
    Prueba_2()
    print("\n  ✓ Todos los ejemplos completados. Gráficas en output/\n")
