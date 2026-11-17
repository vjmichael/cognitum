"""Compatibility import for the recovered diagonal SSM research reference.

Use the later hardened implementation, not the earlier duplicated kernel.
This is not a trained selective SSM and is not a registered Lu capability.
"""
from cognitum.specialists.ssm import (
    DiagonalSSM, InvalidSSM, MAX_DIMS, MAX_ELEMENT, MAX_STATE, MAX_STEPS,
    scan_request,
)

__all__ = ["DiagonalSSM", "InvalidSSM", "MAX_DIMS", "MAX_ELEMENT",
           "MAX_STATE", "MAX_STEPS", "scan_request"]
