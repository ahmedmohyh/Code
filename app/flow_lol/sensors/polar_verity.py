"""Polar Verity Sense support has been removed from this project.

Only the Polar H10 chest belt is used for ECG streaming.
This file is kept as a placeholder so existing imports do not crash; it will be
removed in a future cleanup pass.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

logger.warning(
    "Polar Verity Sense support was removed; only Polar H10 is supported."
)


class PolarVeritySenseStream:
    """Deprecated stub. Do not use."""

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("Polar Verity Sense support has been removed")
