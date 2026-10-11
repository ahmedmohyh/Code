"""Blocking scanner dialog for selecting a Polar H10 device.

Runs bleak discovery in a background thread so the UI stays responsive.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from bleak import BleakScanner

logger = logging.getLogger(__name__)


class _ScanWorker(QThread):
    finished = pyqtSignal(list, str)

    def __init__(self, timeout: float = 10.0, parent: Optional[object] = None) -> None:
        super().__init__(parent)
        self.timeout = timeout

    def run(self) -> None:
        try:
            devices = asyncio.run(BleakScanner.discover(timeout=self.timeout))
            polar = [
                (d.address, d.name or "Unknown")
                for d in devices
                if d.name and "Polar" in d.name
            ]
            error = "" if polar else "No Polar devices found. Make sure the H10 is blinking blue."
            self.finished.emit(polar, error)
        except Exception as exc:
            logger.exception("H10 scan failed")
            self.finished.emit([], f"Scan error: {exc}")


class PolarScanner(QDialog):
    """Dialog that scans for Polar H10 devices and lets the user pick one."""

    def __init__(self, parent: Optional[object] = None, timeout: float = 10.0) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Polar H10")
        self.setMinimumSize(400, 300)
        self.timeout = timeout
        self.selected_address: Optional[str] = None
        self.selected_name: Optional[str] = None
        self.error_message: str = ""

        self._build_ui()
        self._start_scan()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.status_label = QLabel("Scanning for Polar H10 devices...")
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        self.device_list = QListWidget()
        self.device_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.device_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.device_list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_selected)
        buttons.rejected.connect(self.reject)
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setEnabled(False)
        layout.addWidget(buttons)

        self.retry_btn = QPushButton("Retry scan")
        self.retry_btn.clicked.connect(self._start_scan)
        layout.addWidget(self.retry_btn)

    def _start_scan(self) -> None:
        self.device_list.clear()
        self.status_label.setText("Scanning for Polar H10 devices...")
        self.progress.setRange(0, 0)
        self.ok_button.setEnabled(False)
        self.error_message = ""

        self.worker = _ScanWorker(timeout=self.timeout, parent=self)
        self.worker.finished.connect(self._on_scan_finished)
        self.worker.start()

    def _on_scan_finished(self, devices: List[tuple[str, str]], error: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.error_message = error

        if not devices:
            self.status_label.setText(error or "No Polar devices found.")
            return

        self.status_label.setText(f"Found {len(devices)} Polar device(s). Select one.")
        for address, name in devices:
            item = QListWidgetItem(f"{name} – {address}")
            item.setData(Qt.ItemDataRole.UserRole, (address, name))
            self.device_list.addItem(item)
        self.device_list.setCurrentRow(0)
        self.ok_button.setEnabled(True)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        self.ok_button.setEnabled(True)

    def _accept_selected(self) -> None:
        item = self.device_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Select device", "Please select a device.")
            return
        address, name = item.data(Qt.ItemDataRole.UserRole)
        self.selected_address = address
        self.selected_name = name
        self.accept()
