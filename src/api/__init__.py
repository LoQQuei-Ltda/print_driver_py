"""
Módulo para comunicação com APIs externas
"""
from .client import APIClient, APIError

__all__ = [
    "APIClient",
    "APIError"
]
