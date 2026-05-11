"""
geometry/bates.py
-----------------
BATES (Ballistic Test and Evaluation System) grain geometry.

A BATES grain consists of N cylindrical segments, each with:
  • Outer diameter D  (= casing inner diameter, inhibited / bonded)
  • Inner port diameter d₀  (initial)
  • Segment length Lg

Burning surfaces (per segment):
  • Inner cylindrical surface  → Ab_cyl = π · d · Lg
  • Two end faces (if uninhibited) → Ab_ends = 2 · π/4 · (D² − d²)

Regression (both surfaces advance at burn rate r simultaneously):
  • Port grows radially:  d(t) = d₀ + 2·∫r dt
  • Length shrinks (if ends not inhibited): Lg(t) = Lg₀ − 2·∫r dt

Burnout when d ≥ D  OR  Lg ≤ 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

from .base_grain import GrainGeometry, GrainState


# ─────────────────────────────────────────────────────────────────────────────
# Single segment descriptor
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BatesSegment:
    """
    Geometry of one BATES segment (all dimensions in metres).

    Parameters
    ----------
    outer_diameter   : D   [m] — casing inner diameter (inhibited surface)
    inner_diameter   : d₀  [m] — initial port diameter
    length           : Lg  [m] — segment length
    inhibited_ends   : bool    — if True end-faces do not burn
    """

    outer_diameter: float
    inner_diameter: float
    length: float
    inhibited_ends: bool = False

    # ── Derived geometry ──────────────────────────────────────────────────────

    @property
    def web_thickness(self) -> float:
        """Radial web thickness w = (D − d₀)/2  [m]."""
        return (self.outer_diameter - self.inner_diameter) / 2.0

    @property
    def initial_port_area(self) -> float:
        """Initial port cross-section area [m²]."""
        return math.pi / 4.0 * self.inner_diameter ** 2

    @property
    def initial_volume(self) -> float:
        """Initial propellant volume [m³]."""
        return math.pi / 4.0 * (self.outer_diameter**2 - self.inner_diameter**2) * self.length

    # ── Validation ────────────────────────────────────────────────────────────

    def validate(self) -> None:
        if self.inner_diameter <= 0:
            raise ValueError(f"inner_diameter must be > 0 (got {self.inner_diameter*1000:.2f} mm)")
        if self.outer_diameter <= self.inner_diameter:
            raise ValueError(
                f"outer_diameter ({self.outer_diameter*1000:.2f} mm) must be "
                f"> inner_diameter ({self.inner_diameter*1000:.2f} mm)"
            )
        if self.length <= 0:
            raise ValueError(f"Segment length must be > 0 (got {self.length*1000:.2f} mm)")
        # Practical lower bound: port/outer ratio should be < 0.9
        ratio = self.inner_diameter / self.outer_diameter
        if ratio > 0.90:
            raise ValueError(
                f"Port-to-outer ratio {ratio:.2f} is too high (> 0.90). "
                f"Web thickness would be negligible."
            )

    def __str__(self) -> str:
        ends = "inhibited" if self.inhibited_ends else "uninhibited"
        return (
            f"BatesSegment(D={self.outer_diameter*1000:.1f} mm, "
            f"d0={self.inner_diameter*1000:.1f} mm, "
            f"Lg={self.length*1000:.1f} mm, "
            f"w={self.web_thickness*1000:.1f} mm, ends={ends})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# BATES grain
# ─────────────────────────────────────────────────────────────────────────────

class BatesGrain(GrainGeometry):
    """
    N-segment BATES grain.

    Construction
    ------------
    Use `BatesGrain.uniform(...)` for N identical segments, or pass a list of
    `BatesSegment` objects for a mixed / non-uniform configuration.
    """

    geometry_name: str = "BATES"

    def __init__(self, segments: List[BatesSegment]) -> None:
        if not segments:
            raise ValueError("At least one BatesSegment is required.")
        for s in segments:
            s.validate()

        # All segments must share the same outer diameter (same casing)
        D_ref = segments[0].outer_diameter
        for i, s in enumerate(segments[1:], 1):
            if abs(s.outer_diameter - D_ref) > 1e-6:
                raise ValueError(
                    f"Segment {i} outer_diameter ({s.outer_diameter*1000:.2f} mm) "
                    f"differs from segment 0 ({D_ref*1000:.2f} mm). "
                    f"All segments must share the same outer diameter (casing ID)."
                )
        self._segments: List[BatesSegment] = segments

    # ── Alternative constructors ──────────────────────────────────────────────

    @classmethod
    def uniform(
        cls,
        n_segments: int,
        outer_diameter: float,
        inner_diameter: float,
        segment_length: float,
        inhibited_ends: bool = False,
    ) -> "BatesGrain":
        """
        Build N identical BATES segments.

        Parameters
        ----------
        n_segments      : int   — number of segments
        outer_diameter  : float — D  [m]
        inner_diameter  : float — d₀ [m]
        segment_length  : float — Lg [m] per segment
        inhibited_ends  : bool
        """
        if n_segments < 1:
            raise ValueError("n_segments must be ≥ 1")
        segs = [
            BatesSegment(outer_diameter, inner_diameter, segment_length, inhibited_ends)
            for _ in range(n_segments)
        ]
        return cls(segs)

    # ── GrainGeometry interface ───────────────────────────────────────────────

    def get_outer_diameter(self) -> float:
        return self._segments[0].outer_diameter

    def initial_state(self) -> GrainState:
        return self.regress(0.0)

    def regress(self, web_burned: float) -> GrainState:
        """
        Compute grain state after `web_burned` [m] of regression.

        Each surface (inner cylinder + ends if uninhibited) advances
        simultaneously at the same linear burn rate.
        """
        total_Ab = 0.0
        total_Vg = 0.0
        total_Ap = 0.0
        min_web_remaining = math.inf
        any_active = False

        for seg in self._segments:
            D = seg.outer_diameter

            # Current port diameter (grows with regression)
            d_cur = seg.inner_diameter + 2.0 * web_burned

            # Current segment length (shrinks if ends burn)
            if seg.inhibited_ends:
                Lg_cur = seg.length
            else:
                Lg_cur = seg.length - 2.0 * web_burned

            # ── Burnout check ─────────────────────────────────────────────────
            radial_web = seg.web_thickness - web_burned      # remaining radial web
            if seg.inhibited_ends:
                axial_web = math.inf                         # never burns axially
            else:
                axial_web = seg.length / 2.0 - web_burned   # remaining axial half-web

            # Clamp to physical bounds
            if d_cur >= D or radial_web <= 0.0:
                continue   # this segment burned out radially
            if Lg_cur <= 0.0 or axial_web <= 0.0:
                continue   # burned out axially

            any_active = True
            min_web_remaining = min(min_web_remaining, radial_web, axial_web)

            # ── Burning surface area ──────────────────────────────────────────
            Ab_inner = math.pi * d_cur * Lg_cur
            Ab_ends = (
                0.0
                if seg.inhibited_ends
                else 2.0 * (math.pi / 4.0) * (D**2 - d_cur**2)
            )
            total_Ab += Ab_inner + Ab_ends

            # ── Remaining propellant volume ───────────────────────────────────
            total_Vg += (math.pi / 4.0) * (D**2 - d_cur**2) * Lg_cur

            # ── Port flow area ────────────────────────────────────────────────
            total_Ap += math.pi / 4.0 * d_cur**2

        return GrainState(
            burning_area=total_Ab,
            volume=total_Vg,
            port_area=total_Ap,
            web_remaining=max(0.0, min_web_remaining) if any_active else 0.0,
            is_burned_out=not any_active,
        )

    def total_propellant_mass(self, density: float) -> float:
        total_vol = sum(s.initial_volume for s in self._segments)
        return density * total_vol

    def max_web_thickness(self) -> float:
        return max(s.web_thickness for s in self._segments)

    # ── Info / display ────────────────────────────────────────────────────────

    @property
    def n_segments(self) -> int:
        return len(self._segments)

    @property
    def segments(self) -> List[BatesSegment]:
        return list(self._segments)

    def summary(self) -> str:
        s0 = self._segments[0]
        state0 = self.initial_state()
        lines = [
            f"BATES Grain ({self.n_segments} segment{'s' if self.n_segments > 1 else ''})",
            f"  Outer diameter    D  = {s0.outer_diameter*1000:.2f} mm",
        ]
        if self.n_segments == 1 or all(
            s.inner_diameter == s0.inner_diameter for s in self._segments
        ):
            lines.append(f"  Port diameter     d0 = {s0.inner_diameter*1000:.2f} mm")
        else:
            lines.append("  Port diameters (mixed):")
            for i, s in enumerate(self._segments):
                lines.append(f"    Seg {i+1}: d0 = {s.inner_diameter*1000:.2f} mm")
        lines += [
            f"  Segment length    Lg = {s0.length*1000:.2f} mm",
            f"  Web thickness     w  = {s0.web_thickness*1000:.2f} mm",
            f"  Ends inhibited       = {s0.inhibited_ends}",
            f"  Initial Ab        Ab0 = {state0.burning_area*1e4:.2f} cm2",
            f"  Initial volume    Vg0 = {state0.volume*1e6:.2f} cm3",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        s0 = self._segments[0]
        return (
            f"BatesGrain(N={self.n_segments}, "
            f"D={s0.outer_diameter*1000:.1f} mm, "
            f"d0={s0.inner_diameter*1000:.1f} mm, "
            f"Lg={s0.length*1000:.1f} mm)"
        )
