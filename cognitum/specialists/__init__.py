"""First-party, single-distribution HDC / KAN / SSM specialist kernels.

Bundling does not imply automatic selection, scientific reliability or user authority.
"""
from .ssm import DiagonalSSM, InvalidSSM, scan_request
__all__ = ['DiagonalSSM','InvalidSSM','scan_request']
