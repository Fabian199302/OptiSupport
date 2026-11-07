# archivo: config/__init__.py
"""Paquete de configuracion compartida de OptiSupport.

Expone los parametros canonicos del sistema (lambda, mu, c, pool) para que
tanto la API REST (`sistema_real/`) como el modelo SimPy (`simulacion/`)
consuman EXACTAMENTE los mismos valores y no vuelva a ocurrir la
inconsistencia de tasas detectada en la Entrega 1.
"""
from .parametros import P  # noqa: F401