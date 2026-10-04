r"""CLI utility to scan for Polar BLE devices.

Run from the app folder after installing dependencies::

    cd C:\Users\user\Downloads\Masterthesis\Code\app
    .venv\Scripts\activate
    python scripts\scan_polar.py

This prints addresses and names of nearby Polar H10 and Verity Sense devices.
"""

from __future__ import annotations

import asyncio
import logging

from bleak import BleakScanner

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def scan(timeout: float = 10.0) -> None:
    logger.info("Scanning for Polar BLE devices for %.0f seconds...", timeout)
    devices = await BleakScanner.discover(timeout=timeout)
    found = False
    for d in devices:
        name = d.name or ""
        if "Polar" in name:
            found = True
            logger.info("  %s - %s", d.address, name)
    if not found:
        logger.info("No Polar devices found.")


if __name__ == "__main__":
    asyncio.run(scan())
