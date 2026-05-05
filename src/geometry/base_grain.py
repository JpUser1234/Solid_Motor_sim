"""
geometry/base_grain.py
----------------------
Abstract base class for all solid rocket motor grain geometries.

To add a new geometry (e.g. Star, Finocyl):
  1. Create a new module in geometry/
  2. Subclass GrainGeometry
  3. Implement: initial_state(), regress(), get_outer_diameter(),
                total_propellant_mass(), geometry_name
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────────────────
# Grain state snapshot
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GrainState:
    """
    Snapshot of a grain's geometric state at a given regression depth.

    All values are totals across all segments.
    """
    burning_area: float      # Ab  [m²]  — total burning surface area
    volume: float            # Vg  [m³]  — remaining propellant volume
    port_area: float         # Ap  [m²]  — total port (flow) cross-section
    web_remaining: float     # w   [m]   — smallest remaining web thickness
    is_burned_out: bool      # True when no surface remains


# ─────────────────────────────────────────────────────────────────────────────
# Abstract geometry interface
# ─────────────────────────────────────────────────────────────────────────────

class GrainGeometry(ABC):
    """
    Interface that every grain geometry must implement.

    The simulator calls `regress(web_burned)` at every time step, where
    `web_burned` is the cumulative thickness consumed since ignition [m].
    """

    # ── Required properties ───────────────────────────────────────────────────

    @property
    @abstractmethod
    def geometry_name(self) -> str:
        """Short human-readable name (e.g. 'BATES', 'Star')."""
        ...

    # ── Required methods ──────────────────────────────────────────────────────

    @abstractmethod
    def initial_state(self) -> GrainState:
        """GrainState at t=0 (zero regression)."""
        ...

    @abstractmethod
    def regress(self, web_burned: float) -> GrainState:
        """
        Return the GrainState after `web_burned` [m] of uniform regression
        from all burning surfaces (normal to surface).
        """
        ...

    @abstractmethod
    def get_outer_diameter(self) -> float:
        """Outer diameter of the grain = motor casing inner diameter [m]."""
        ...

    @abstractmethod
    def total_propellant_mass(self, density: float) -> float:
        """
        Initial total propellant mass [kg].

        Parameters
        ----------
        density : float — propellant density [kg/m³].
        """
        ...

    # ── Optional / convenience ────────────────────────────────────────────────

    def max_web_thickness(self) -> float:
        """
        Maximum radial web thickness [m].
        Override in subclass for a precise value; default uses initial state.
        """
        return self.initial_state().web_remaining

    def __repr__(self) -> str:
        return (
            f"{self.geometry_name}Grain("
            f"D={self.get_outer_diameter()*1000:.1f} mm, "
            f"Ab0={self.initial_state().burning_area*1e4:.1f} cm²)"
        )
