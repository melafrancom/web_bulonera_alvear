"""
ERP Client Exceptions
"""


class ERPUnavailableError(Exception):
    """El ERP no está disponible o no responde"""
    pass


class ERPAuthError(Exception):
    """Error de autenticación con el ERP"""
    pass


class ERPValidationError(Exception):
    """Error de validación de datos del ERP"""
    pass


class ERPTimeoutError(Exception):
    """Timeout en la comunicación con el ERP"""
    pass
