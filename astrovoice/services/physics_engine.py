import numpy as np
import scipy.constants as const

class PhysicsEngine:
    """Mathematical precision engine for astrophysics calculations."""
    
    @staticmethod
    def schwarzschild_radius(mass_kg: float) -> float:
        """Calculate Schwarzschild radius: Rs = 2GM / c^2"""
        G = const.G
        c = const.c
        return (2 * G * mass_kg) / (c**2)

    @staticmethod
    def rocket_equation(isp: float, m_initial: float, m_final: float) -> float:
        """Tsiolkovsky rocket equation: delta_v = Isp * g0 * ln(mi/mf)"""
        g0 = 9.80665
        return isp * g0 * np.log(m_initial / m_final)

    @staticmethod
    def escape_velocity(mass_kg: float, radius_m: float) -> float:
        """Calculate escape velocity: ve = sqrt(2GM / r)"""
        G = const.G
        return np.sqrt((2 * G * mass_kg) / radius_m)

    @staticmethod
    def orbital_velocity(mass_kg: float, radius_m: float) -> float:
        """Calculate circular orbital velocity: vo = sqrt(GM / r)"""
        G = const.G
        return np.sqrt((G * mass_kg) / radius_m)
