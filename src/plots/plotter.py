"""
plots/plotter.py
----------------
All visualisation functions for the solid motor simulator.

Functions
---------
plot_thrust_curve()          — F vs t
plot_chamber_pressure()      — Pc vs t
plot_burning_area_kn()       — Ab and Kn vs t
plot_mass_flow()             — ṁ vs t
plot_efficiency_breakdown()  — bar chart of efficiency components
plot_full_dashboard()        — 2×3 grid of all key plots
save_all_plots()             — save every figure to disk
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as ticker
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

from src.motor.simulation import SimulationResult

# ─────────────────────────────────────────────────────────────────────────────
# Global style
# ─────────────────────────────────────────────────────────────────────────────

_PALETTE = {
    "thrust":    "#E84040",
    "pressure":  "#3A7FD5",
    "area":      "#F5A623",
    "kn":        "#7B61FF",
    "mass":      "#27AE60",
    "cf":        "#E67E22",
    "efficiency":["#3A7FD5", "#E84040", "#F5A623", "#27AE60"],
}

_RCPARAMS = {
    "figure.dpi": 130,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "font.family": "DejaVu Sans",
    "lines.linewidth": 2.0,
}


def _apply_style() -> None:
    plt.rcParams.update(_RCPARAMS)


def _style_ax(ax: plt.Axes) -> None:
    """Minimal post-processing for a single axes."""
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)
    ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
    ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())


# ─────────────────────────────────────────────────────────────────────────────
# Individual plots
# ─────────────────────────────────────────────────────────────────────────────

def plot_thrust_curve(
    result: SimulationResult,
    ax: Optional[plt.Axes] = None,
    vacuum: bool = False,
    compare_vacuum: bool = False,
    label: str = "",
) -> plt.Axes:
    """Thrust vs time (SL or vacuum)."""
    _apply_style()
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(9, 4))

    if compare_vacuum:
        ax.plot(result.time, result.thrust, color=_PALETTE["thrust"], label="Thrust (SL)")
        ax.plot(result.time, result.thrust_vacuum, color=_PALETTE["thrust"], linestyle="--", label="Thrust (vacuum)")
        F = result.thrust_vacuum
    else:
        F = result.thrust_vacuum if vacuum else result.thrust
        lbl = label or ("Thrust (vacuum)" if vacuum else "Thrust (SL)")
        ax.plot(result.time, F, color=_PALETTE["thrust"], label=lbl)
    ax.set_xlabel("Time  [s]")
    ax.set_ylabel("Thrust  [N]")
    ax.set_title("Thrust vs Time")
    ax.legend()
    ax.margins(x=0.02, y=0.12)
    _style_ax(ax)

    # Zoomed inset to make the curve shape readable in static exports.
    if result.time.size >= 4:
        axins = inset_axes(ax, width="42%", height="42%", loc="upper right", borderpad=1.0)
        axins.plot(result.time, result.thrust, color=_PALETTE["thrust"], linewidth=1.4)
        axins.plot(result.time, result.thrust_vacuum, color=_PALETTE["thrust"], linestyle="--", linewidth=1.2)
        peak_idx = int(np.argmax(F))
        peak_t = float(result.time[peak_idx])
        zoom_half_width = max(0.18, 0.18 * float(result.burn_time))
        x0 = max(0.0, peak_t - zoom_half_width)
        x1 = min(float(result.burn_time), peak_t + zoom_half_width)
        y_peak = float(np.max(result.thrust_vacuum if compare_vacuum or vacuum else result.thrust))
        axins.set_xlim(x0, x1)
        axins.set_ylim(max(0.0, 0.65 * y_peak), 1.05 * y_peak)
        axins.grid(True, alpha=0.18, linestyle="--")
        axins.tick_params(labelsize=7)

    # Annotate max thrust
    idx_max = int(np.argmax(F))
    ax.annotate(
        f"F_max = {F[idx_max]:.1f} N",
        xy=(result.time[idx_max], F[idx_max]),
        xytext=(result.time[idx_max] + result.burn_time * 0.05, F[idx_max] * 0.95),
        fontsize=8,
        arrowprops=dict(arrowstyle="->", color="gray", lw=0.8),
    )

    if standalone:
        plt.tight_layout()
    return ax


def plot_chamber_pressure(
    result: SimulationResult,
    ax: Optional[plt.Axes] = None,
    label: str = "",
    ambient_pressure_pa: Optional[float] = None,
    ambient_label: str = "Ambient pressure",
) -> plt.Axes:
    """Chamber pressure vs time."""
    _apply_style()
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(9, 4))

    Pc_MPa = result.chamber_pressure / 1.0e6
    ax.plot(result.time, Pc_MPa, color=_PALETTE["pressure"], label=label or "Pc")
    if ambient_pressure_pa is not None:
        ax.axhline(ambient_pressure_pa / 1.0e6, color="#666", linestyle="--", linewidth=1.2, label=ambient_label)
    ax.set_xlabel("Time  [s]")
    ax.set_ylabel("Chamber Pressure  [MPa]")
    ax.set_title("Chamber Pressure vs Time")
    ax.legend()
    ax.margins(x=0.02, y=0.12)
    if Pc_MPa.size:
        ax.set_ylim(0.0, float(np.max(Pc_MPa)) * 1.15)
    _style_ax(ax)

    # Annotate max Pc
    idx_max = int(np.argmax(Pc_MPa))
    ax.annotate(
        f"Pc_max = {Pc_MPa[idx_max]:.3f} MPa",
        xy=(result.time[idx_max], Pc_MPa[idx_max]),
        xytext=(result.time[idx_max] + result.burn_time * 0.05, Pc_MPa[idx_max] * 0.92),
        fontsize=8,
        arrowprops=dict(arrowstyle="->", color="gray", lw=0.8),
    )

    if standalone:
        plt.tight_layout()
    return ax


def plot_burning_area_kn(
    result: SimulationResult,
    axes: Optional[tuple[plt.Axes, plt.Axes]] = None,
) -> tuple[plt.Axes, plt.Axes]:
    """Burning area and Klemmung (Kn) vs time — side by side."""
    _apply_style()
    standalone = axes is None
    if standalone:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    else:
        ax1, ax2 = axes

    ax1.plot(result.time, result.burning_area * 1.0e4, color=_PALETTE["area"])
    ax1.set_xlabel("Time  [s]")
    ax1.set_ylabel("Burning Area  [cm²]")
    ax1.set_title("Burning Area Ab vs Time")
    _style_ax(ax1)

    ax2.plot(result.time, result.klemung, color=_PALETTE["kn"])
    ax2.set_xlabel("Time  [s]")
    ax2.set_ylabel("Kn = Ab / At  [−]")
    ax2.set_title("Klemmung (Kn) vs Time")
    _style_ax(ax2)

    if standalone:
        plt.tight_layout()
    return ax1, ax2


def plot_mass_flow(
    result: SimulationResult,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """Mass flow rate vs time."""
    _apply_style()
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(9, 4))

    ax.plot(result.time, result.mass_flow, color=_PALETTE["mass"])
    ax.set_xlabel("Time  [s]")
    ax.set_ylabel("Mass Flow Rate  [kg/s]")
    ax.set_title("Mass Flow Rate vs Time")
    _style_ax(ax)

    if standalone:
        plt.tight_layout()
    return ax


def plot_efficiency_breakdown(
    result: SimulationResult,
    eta_cstar: float,
    eta_cf: float,
    lambda_div: float,
    ax: Optional[plt.Axes] = None,
) -> plt.Axes:
    """
    Horizontal bar chart showing efficiency component breakdown.

    Parameters
    ----------
    eta_cstar   : ηc*  — combustion efficiency
    eta_cf      : ηCF  — nozzle efficiency
    lambda_div  : λ    — divergence correction
    """
    _apply_style()
    standalone = ax is None
    if standalone:
        fig, ax = plt.subplots(figsize=(8, 4))

    labels = ["ηc*\n(Combustion)", "ηCF\n(Nozzle)", "λ\n(Divergence)", "η\n(Delivered)"]
    values = [eta_cstar * 100, eta_cf * 100, lambda_div * 100, result.eta_delivered * 100]
    colors = _PALETTE["efficiency"]

    bars = ax.bar(labels, values, color=colors, width=0.5, edgecolor="white",
                  linewidth=1.5, zorder=3)
    ax.set_ylabel("Efficiency  [%]")
    ax.set_title("Motor Efficiency Breakdown")
    ax.set_ylim(0, 115)
    ax.axhline(100, color="#888", linestyle="--", linewidth=0.9, alpha=0.7, zorder=2)
    ax.grid(axis="y", alpha=0.25, zorder=1)
    ax.grid(axis="x", visible=False)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.5,
            f"{val:.2f}%",
            ha="center", va="bottom",
            fontsize=10, fontweight="bold",
        )

    if standalone:
        plt.tight_layout()
    return ax


# ─────────────────────────────────────────────────────────────────────────────
# Full 2×3 dashboard
# ─────────────────────────────────────────────────────────────────────────────

def plot_full_dashboard(
    result: SimulationResult,
    motor_name: str = "Solid Motor",
    eta_cstar: float = 0.95,
    eta_cf: float = 0.97,
    lambda_div: float = 0.983,
) -> plt.Figure:
    """
    2×3 dashboard with all key simulation outputs.

    Layout
    ------
    [Thrust vs t]        [Chamber Pressure vs t]   [Burning Area vs t]
    [Klemmung (Kn) vs t] [Propellant Mass vs t]    [Efficiency Breakdown]
    """
    _apply_style()

    fig = plt.figure(figsize=(17, 9))
    fig.suptitle(
        f"Solid Rocket Motor Simulation — {motor_name}",
        fontsize=14, fontweight="bold", y=0.99,
    )

    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.48, wspace=0.38)

    # ── Row 0 ─────────────────────────────────────────────────────────────────

    ax00 = fig.add_subplot(gs[0, 0])
    ax00.plot(result.time, result.thrust, color=_PALETTE["thrust"], label="Thrust (SL)")
    ax00.plot(result.time, result.thrust_vacuum, color=_PALETTE["thrust"], linestyle="--", label="Thrust (vacuum)")
    ax00.set_xlabel("Time [s]"); ax00.set_ylabel("Thrust [N]")
    ax00.set_title("Thrust")
    ax00.legend()
    _style_ax(ax00)

    ax01 = fig.add_subplot(gs[0, 1])
    ax01.plot(result.time, result.chamber_pressure / 1e6, color=_PALETTE["pressure"], label="Chamber pressure")
    ax01.axhline(0.0, color="#666", linestyle="--", linewidth=1.0, label="Ambient (vacuum)")
    ax01.set_xlabel("Time [s]"); ax01.set_ylabel("Pc [MPa]")
    ax01.set_title("Chamber Pressure")
    ax01.legend()
    _style_ax(ax01)

    ax02 = fig.add_subplot(gs[0, 2])
    ax02.plot(result.time, result.burning_area * 1e4, color=_PALETTE["area"])
    ax02.set_xlabel("Time [s]"); ax02.set_ylabel("Ab [cm²]")
    ax02.set_title("Burning Surface Area")
    _style_ax(ax02)

    # ── Row 1 ─────────────────────────────────────────────────────────────────

    ax10 = fig.add_subplot(gs[1, 0])
    ax10.plot(result.time, result.klemung, color=_PALETTE["kn"])
    ax10.set_xlabel("Time [s]"); ax10.set_ylabel("Kn = Ab/At [−]")
    ax10.set_title("Klemmung (Kn)")
    _style_ax(ax10)

    ax11 = fig.add_subplot(gs[1, 1])
    ax11.plot(result.time, result.propellant_mass * 1000, color=_PALETTE["mass"])
    ax11.set_xlabel("Time [s]"); ax11.set_ylabel("Propellant Mass [g]")
    ax11.set_title("Remaining Propellant")
    _style_ax(ax11)

    ax12 = fig.add_subplot(gs[1, 2])
    plot_efficiency_breakdown(result, eta_cstar, eta_cf, lambda_div, ax=ax12)

    # ── Summary text box ──────────────────────────────────────────────────────
    summary_text = (
        f"It = {result.total_impulse:.1f} N·s  |  "
        f"Isp = {result.specific_impulse_sl:.1f} s  |  "
        f"Fmax = {result.max_thrust:.1f} N  |  "
        f"tb = {result.burn_time:.2f} s  |  "
        f"mp = {result.initial_propellant_mass*1000:.1f} g"
    )
    fig.text(
        0.5, 0.01, summary_text,
        ha="center", va="bottom", fontsize=9,
        style="italic", color="#444",
    )

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Save helpers
# ─────────────────────────────────────────────────────────────────────────────

def save_all_plots(
    result: SimulationResult,
    motor_name: str = "motor",
    output_dir: str = "output",
    eta_cstar: float = 0.95,
    eta_cf: float = 0.97,
    lambda_div: float = 0.983,
    fmt: str = "png",
    dpi: int = 220,
) -> list[str]:
    """
    Save all individual plots + dashboard to `output_dir`.

    Returns list of file paths created.
    """
    os.makedirs(output_dir, exist_ok=True)
    _apply_style()
    saved: list[str] = []

    def _save(fig: plt.Figure, name: str) -> str:
        path = os.path.join(output_dir, f"{motor_name}_{name}.{fmt}")
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        saved.append(path)
        return path

    # Individual
    fig, ax = plt.subplots(figsize=(11, 5)); plot_thrust_curve(result, ax=ax, compare_vacuum=True); _save(fig, "thrust")
    fig, ax = plt.subplots(figsize=(11, 5)); plot_chamber_pressure(result, ax=ax, ambient_pressure_pa=0.0, ambient_label="Ambient (vacuum)"); plt.tight_layout(); _save(fig, "pressure")
    fig, ax = plt.subplots(figsize=(11, 5)); plot_mass_flow(result, ax=ax);          plt.tight_layout(); _save(fig, "mass_flow")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 5)); plot_burning_area_kn(result, (a1, a2)); plt.tight_layout(); _save(fig, "area_kn")
    fig, ax = plt.subplots(figsize=(8, 4));  plot_efficiency_breakdown(result, eta_cstar, eta_cf, lambda_div, ax=ax); plt.tight_layout(); _save(fig, "efficiency")
    fig, ax = plt.subplots(figsize=(11, 5)); plot_thrust_curve(result, ax=ax, vacuum=True); _save(fig, "thrust_vacuum")
    fig, ax = plt.subplots(figsize=(11, 5)); plot_chamber_pressure(result, ax=ax, ambient_pressure_pa=0.0, ambient_label="Ambient (vacuum)"); plt.tight_layout(); _save(fig, "pressure_vacuum")

    # Dashboard
    fig_dash = plot_full_dashboard(result, motor_name, eta_cstar, eta_cf, lambda_div)
    _save(fig_dash, "dashboard")

    print(f"  Saved {len(saved)} plots to '{output_dir}/':")
    for p in saved:
        print(f"    {p}")
    return saved
