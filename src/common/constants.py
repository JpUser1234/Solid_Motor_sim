"""
Central design constants and physical constants.
"""

G0 = 9.80665  # m/s^2
EARTH_RADIUS_M = 6371000.0  # m
R_AIR = 287.05  # J/(kg·K)
G_CONST = 6.67430e-11  # m^3 kg^-1 s^-2
EARTH_MASS_KG = 5.97219e24  # kg

# ISA reference
ISA_T0 = 288.15  # K
ISA_P0 = 101325.0  # Pa
ISA_LAPSE = 0.0065  # K/m


__all__ = [
    "G0", "EARTH_RADIUS_M", "R_AIR", "G_CONST", "EARTH_MASS_KG",
    "ISA_T0", "ISA_P0", "ISA_LAPSE",
]
