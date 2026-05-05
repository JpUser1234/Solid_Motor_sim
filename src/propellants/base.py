"""
propellants/base.py
-------------------
Dataclass that holds all thermophysical and ballistic properties
for a solid propellant.  All values in SI units internally.
"""

from dataclasses import dataclass, field


@dataclass
class PropellantProperties:
    """
    Complete propellant description for a solid rocket motor simulation.

    Burn rate law (Saint-Robert / Vieille):
        r [m/s] = burn_rate_coefficient [m/s/Pa^n] × Pc [Pa] ^ burn_rate_exponent

    Temperature correction (optional):
        r(T) = r_ref × (1 + temperature_sensitivity × (T − T_ref))
    """

    name: str

    # ── Ballistic properties ──────────────────────────────────────────────────
    burn_rate_coefficient: float   # a  [m/s / Pa^n]  — stored in SI
    burn_rate_exponent: float      # n  [−]

    # ── Propellant physical properties ───────────────────────────────────────
    density: float                 # ρp [kg/m³]

    # ── Thermochemical properties ─────────────────────────────────────────────
    c_star: float                  # c* [m/s]  — theoretical characteristic velocity
    gamma: float                   # γ  [−]    — specific heat ratio of combustion gases
    molar_mass: float              # M  [g/mol]— mean molar mass of combustion gases
    flame_temperature: float       # Tf [K]    — adiabatic flame temperature

    # ── Temperature sensitivity ───────────────────────────────────────────────
    temperature_sensitivity: float = 0.0     # σp [1/K]
    reference_temperature: float = 298.15    # T_ref [K]

    # ── Derived ───────────────────────────────────────────────────────────────
    @property
    def gas_constant(self) -> float:
        """Specific gas constant R [J/(kg·K)] = R_u / M."""
        return 8314.46 / self.molar_mass

    # ── Burn rate ─────────────────────────────────────────────────────────────
    def burn_rate(self, pressure_pa: float, temperature_k: float | None = None) -> float:
        """
        Instantaneous burn rate [m/s].

        Parameters
        ----------
        pressure_pa : float
            Chamber pressure in Pa.
        temperature_k : float, optional
            Propellant initial temperature in K (for temp. correction).

        Returns
        -------
        float : burn rate in m/s.
        """
        if pressure_pa <= 0:
            return 0.0
        r = self.burn_rate_coefficient * (pressure_pa ** self.burn_rate_exponent)
        if temperature_k is not None and self.temperature_sensitivity != 0.0:
            r *= 1.0 + self.temperature_sensitivity * (temperature_k - self.reference_temperature)
        return r

    def c_star_at_efficiency(self, eta_cstar: float) -> float:
        """Effective c* after applying combustion efficiency."""
        return self.c_star * eta_cstar

    def __str__(self) -> str:  # pragma: no cover
        return (
            f"Propellant : {self.name}\n"
            f"  a   = {self.burn_rate_coefficient:.4e} m/s/Pa^n\n"
            f"  n   = {self.burn_rate_exponent:.4f}\n"
            f"  ρp  = {self.density:.1f} kg/m³\n"
            f"  c*  = {self.c_star:.1f} m/s\n"
            f"  γ   = {self.gamma:.4f}\n"
            f"  M   = {self.molar_mass:.2f} g/mol\n"
            f"  Tf  = {self.flame_temperature:.0f} K\n"
            f"  R   = {self.gas_constant:.2f} J/(kg·K)"
        )
