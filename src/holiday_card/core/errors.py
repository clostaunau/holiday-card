"""Exceptions shared by the compiler and the modules it composes."""

from __future__ import annotations


class UnsupportedFeatureError(NotImplementedError):
    """Raised when the compiler encounters a Card feature not yet ported.

    The error message names the feature and the element for easy triage.
    """
