"""
ERP Client Package

Cliente HTTP puro para comunicación con el ERP.
NO se registra en INSTALLED_APPS - es un módulo Python puro sin modelos.
"""
from .client import ERPClient
from .exceptions import ERPUnavailableError, ERPAuthError

__all__ = ['ERPClient', 'ERPUnavailableError', 'ERPAuthError']
