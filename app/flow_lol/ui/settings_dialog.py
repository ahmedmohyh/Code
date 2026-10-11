"""Settings / configuration dialog with modern card-styled tabs."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flow_lol.config.settings import AppSettings
from flow_lol.sensors.scanner import PolarScanner
from flow_lol.ui.components import CardWidget
from flow_lol.ui.styles import Colors, Spacing


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Flow-LoL Settings")
        self.setMinimumSize(720, 560)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"background: {Colors.BG};")

        # Work on a copy so Cancel discards changes.
        self.settings = AppSettings(**settings.__dict__)

        tabs = QTabWidget()
        tabs.addTab(self._sensors_tab(), "Sensors")
        tabs.addTab(self._paths_tab(), "Storage")
        tabs.addTab(self._game_tab(), "Game / Riot")
        tabs.addTab(self._classifier_tab(), "Classifier")
        tabs.addTab(self._interventions_tab(), "Interventions")
        tabs.addTab(self._privacy_tab(), "Privacy")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.LG)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _sensors_tab(self) -> QWidget:
        card = CardWidget("Sensors")
        form = QFormLayout()
        form.setSpacing(Spacing.MD)

        self.use_h10_box = QCheckBox("Use Polar H10 chest belt (ECG)")
        self.use_h10_box.setChecked(self.settings.use_h10)
        form.addRow(self.use_h10_box)

        h10_row = QHBoxLayout()
        h10_row.setSpacing(Spacing.SM)
        self.h10_address_edit = QLineEdit(self.settings.h10_address)
        self.h10_address_edit.setPlaceholderText("Scan to set paired MAC address")
        self.h10_address_edit.setReadOnly(True)
        h10_row.addWidget(self.h10_address_edit)

        scan_btn = QPushButton("Scan...")
        scan_btn.clicked.connect(self._scan_h10)
        h10_row.addWidget(scan_btn)
        form.addRow("H10 address:", h10_row)

        self.window_spin = QSpinBox()
        self.window_spin.setRange(10, 300)
        self.window_spin.setValue(self.settings.window_seconds)
        form.addRow("Analysis window (seconds):", self.window_spin)

        self.overlap_spin = QSpinBox()
        self.overlap_spin.setRange(0, 90)
        self.overlap_spin.setValue(self.settings.overlap_percent)
        form.addRow("Window overlap (%):", self.overlap_spin)

        note = QLabel(
            "If the H10 is already paired with Windows, set its address above so the "
            "app can connect directly without scanning. Leave it empty to scan each time."
        )
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        form.addRow(note)

        card.content_layout().addLayout(form)
        return card

    def _scan_h10(self) -> None:
        scanner = PolarScanner(self)
        if scanner.exec() == QDialog.DialogCode.Accepted and scanner.selected_address:
            self.h10_address_edit.setText(scanner.selected_address)
            QMessageBox.information(
                self, "H10 found", f"Selected {scanner.selected_name or scanner.selected_address}."
            )
        elif scanner.error_message:
            QMessageBox.warning(self, "Scan failed", scanner.error_message)

    def _paths_tab(self) -> QWidget:
        card = CardWidget("Storage")
        form = QFormLayout()
        form.setSpacing(Spacing.MD)

        self.ecg_path_edit = QLineEdit(self.settings.ecg_save_path)
        self.ecg_path_edit.setReadOnly(True)
        ecg_btn = QPushButton("Browse...")
        ecg_btn.clicked.connect(self._browse_ecg_path)
        ecg_row = QHBoxLayout()
        ecg_row.setSpacing(Spacing.SM)
        ecg_row.addWidget(self.ecg_path_edit)
        ecg_row.addWidget(ecg_btn)
        form.addRow("ECG save folder:", ecg_row)

        self.webcam_path_edit = QLineEdit(self.settings.webcam_save_path)
        self.webcam_path_edit.setReadOnly(True)
        webcam_btn = QPushButton("Browse...")
        webcam_btn.clicked.connect(self._browse_webcam_path)
        webcam_row = QHBoxLayout()
        webcam_row.setSpacing(Spacing.SM)
        webcam_row.addWidget(self.webcam_path_edit)
        webcam_row.addWidget(webcam_btn)
        form.addRow("Webcam save folder:", webcam_row)

        self.logs_path_edit = QLineEdit(self.settings.logs_save_path)
        self.logs_path_edit.setReadOnly(True)
        logs_btn = QPushButton("Browse...")
        logs_btn.clicked.connect(self._browse_logs_path)
        logs_row = QHBoxLayout()
        logs_row.setSpacing(Spacing.SM)
        logs_row.addWidget(self.logs_path_edit)
        logs_row.addWidget(logs_btn)
        form.addRow("Logs save folder:", logs_row)

        self.db_path_edit = QLineEdit(self.settings.db_path)
        self.db_path_edit.setReadOnly(True)
        db_btn = QPushButton("Browse...")
        db_btn.clicked.connect(self._browse_db_path)
        db_row = QHBoxLayout()
        db_row.setSpacing(Spacing.SM)
        db_row.addWidget(self.db_path_edit)
        db_row.addWidget(db_btn)
        form.addRow("Database path:", db_row)

        self.replay_path_edit = QLineEdit(self.settings.replay_save_path)
        self.replay_path_edit.setReadOnly(True)
        replay_btn = QPushButton("Browse...")
        replay_btn.clicked.connect(self._browse_replay_path)
        replay_row = QHBoxLayout()
        replay_row.setSpacing(Spacing.SM)
        replay_row.addWidget(self.replay_path_edit)
        replay_row.addWidget(replay_btn)
        form.addRow("LoL replay folder:", replay_row)

        self.webcam_enabled_box = QCheckBox("Record webcam during sessions")
        self.webcam_enabled_box.setChecked(self.settings.webcam_enabled)
        form.addRow(self.webcam_enabled_box)

        note = QLabel(
            "Changes to storage paths take effect after restarting the app. "
            "Existing recordings stay in their original locations."
        )
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        form.addRow(note)

        card.content_layout().addLayout(form)
        return card

    def _game_tab(self) -> QWidget:
        card = CardWidget("Game / Riot")
        form = QFormLayout()
        form.setSpacing(Spacing.MD)

        self.auto_detect_box = QCheckBox("Auto-detect LoL match start/stop")
        self.auto_detect_box.setChecked(self.settings.auto_detect_game)
        form.addRow(self.auto_detect_box)

        note = QLabel(
            "Auto-detect uses the local League Client (LCU) API first: no Riot API key is needed. "
            "If the client is closed, the app falls back to LoL-process detection, then to manual start/stop."
        )
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        form.addRow(note)

        # Riot REST API is not used; visually de-emphasize it.
        riot_group = CardWidget("Riot Games REST API (not used)")
        riot_layout = QFormLayout()
        riot_layout.setSpacing(Spacing.MD)

        self.riot_enabled_box = QCheckBox("Enable Riot Games API (requires API key)")
        self.riot_enabled_box.setChecked(self.settings.riot_api_enabled)
        self.riot_enabled_box.setEnabled(False)
        riot_layout.addRow(self.riot_enabled_box)

        self.riot_key_edit = QLineEdit(self.settings.riot_api_key)
        self.riot_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.riot_key_edit.setEnabled(False)
        riot_layout.addRow("Riot API key:", self.riot_key_edit)

        riot_group.content_layout().addLayout(riot_layout)
        form.addRow(riot_group)

        card.content_layout().addLayout(form)
        return card

    def _classifier_tab(self) -> QWidget:
        card = CardWidget("Classifier ensemble")
        layout = QVBoxLayout()
        layout.setSpacing(Spacing.SM)

        intro = QLabel(
            "Five ECG-only models vote with a hard majority. "
            "Enable an odd number so the vote always has a winner."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        layout.addWidget(intro)

        self.use_biraffe2_svm_box = QCheckBox("BIRAFFE2 SVM (AUC 0.790)")
        self.use_biraffe2_svm_box.setChecked(self.settings.use_biraffe2_svm)
        layout.addWidget(self.use_biraffe2_svm_box)

        self.use_biraffe2_knn_box = QCheckBox("BIRAFFE2 kNN (AUC 0.761)")
        self.use_biraffe2_knn_box.setChecked(self.settings.use_biraffe2_knn)
        layout.addWidget(self.use_biraffe2_knn_box)

        self.use_biraffe2_rf_box = QCheckBox("BIRAFFE2 RandomForest (AUC 0.725)")
        self.use_biraffe2_rf_box.setChecked(self.settings.use_biraffe2_rf)
        layout.addWidget(self.use_biraffe2_rf_box)

        self.use_irshad_rf_box = QCheckBox("Irshad RandomForest (AUC 0.692)")
        self.use_irshad_rf_box.setChecked(self.settings.use_irshad_rf)
        layout.addWidget(self.use_irshad_rf_box)

        self.use_biraffe2_mlp_box = QCheckBox("BIRAFFE2 MLP deep learning (AUC 0.730)")
        self.use_biraffe2_mlp_box.setChecked(self.settings.use_biraffe2_mlp)
        layout.addWidget(self.use_biraffe2_mlp_box)

        card.content_layout().addLayout(layout)
        return card

    def _interventions_tab(self) -> QWidget:
        card = CardWidget("Interventions")
        layout = QVBoxLayout()
        layout.setSpacing(Spacing.SM)

        self.mute_notifications_box = QCheckBox("Mute system notifications during flow (Phase 10)")
        self.mute_notifications_box.setChecked(self.settings.notification_muting_enabled)
        self.mute_notifications_box.setEnabled(False)
        layout.addWidget(self.mute_notifications_box)

        self.adaptive_cues_box = QCheckBox("Adaptive audio / lighting cues (Phase 10)")
        self.adaptive_cues_box.setChecked(self.settings.adaptive_cues_enabled)
        self.adaptive_cues_box.setEnabled(False)
        layout.addWidget(self.adaptive_cues_box)

        self.edge_status_box = QCheckBox("Screen-edge status only, no in-game overlay (AF-04)")
        self.edge_status_box.setChecked(self.settings.screen_edge_status_enabled)
        layout.addWidget(self.edge_status_box)

        note = QLabel(
            "Full disturbance-reduction features are planned for Phase 10. "
            "Until then the app avoids in-game overlays."
        )
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        layout.addWidget(note)

        card.content_layout().addLayout(layout)
        return card

    def _privacy_tab(self) -> QWidget:
        card = CardWidget("Privacy")
        layout = QVBoxLayout()
        layout.setSpacing(Spacing.MD)

        info = QLabel(
            "All data is processed locally on this PC.<br><br>"
            "ECG recordings, webcam videos, and the SQLite database are stored "
            "under the configured storage folders.<br><br>"
            "You can delete your local data from the Dashboard once deletion is enabled."
        )
        info.setWordWrap(True)
        info.setProperty("role", "muted")
        layout.addWidget(info)

        self.data_delete_btn = QPushButton("Delete all local data...")
        self.data_delete_btn.setEnabled(False)
        layout.addWidget(self.data_delete_btn)
        layout.addStretch()

        card.content_layout().addLayout(layout)
        return card

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _browse_ecg_path(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select ECG save folder", self.ecg_path_edit.text())
        if path:
            self.ecg_path_edit.setText(path)

    def _browse_webcam_path(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select webcam save folder", self.webcam_path_edit.text()
        )
        if path:
            self.webcam_path_edit.setText(path)

    def _browse_logs_path(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select logs save folder", self.logs_path_edit.text()
        )
        if path:
            self.logs_path_edit.setText(path)

    def _browse_db_path(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select SQLite database file",
            self.db_path_edit.text(),
            "SQLite databases (*.db *.sqlite *.sqlite3);;All files (*)",
        )
        if path:
            self.db_path_edit.setText(path)

    def _browse_replay_path(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select LoL replay folder", self.replay_path_edit.text()
        )
        if path:
            self.replay_path_edit.setText(path)

    def _validate_and_accept(self) -> None:
        if not self.use_h10_box.isChecked():
            QMessageBox.warning(self, "Invalid sensors", "Enable the Polar H10 sensor.")
            return

        enabled_classifiers = [
            self.use_biraffe2_svm_box.isChecked(),
            self.use_biraffe2_knn_box.isChecked(),
            self.use_biraffe2_rf_box.isChecked(),
            self.use_irshad_rf_box.isChecked(),
            self.use_biraffe2_mlp_box.isChecked(),
        ]
        if sum(enabled_classifiers) == 0:
            QMessageBox.warning(self, "Invalid classifiers", "Enable at least one classifier.")
            return
        if sum(enabled_classifiers) % 2 == 0:
            QMessageBox.warning(
                self,
                "Invalid ensemble size",
                "Enable an odd number of classifiers so the majority vote always has a winner.",
            )
            return

        self.settings.use_h10 = self.use_h10_box.isChecked()
        self.settings.h10_address = self.h10_address_edit.text().strip()
        self.settings.ecg_save_path = self.ecg_path_edit.text()
        self.settings.webcam_save_path = self.webcam_path_edit.text()
        self.settings.logs_save_path = self.logs_path_edit.text()
        self.settings.db_path = self.db_path_edit.text()
        self.settings.replay_save_path = self.replay_path_edit.text()
        self.settings.webcam_enabled = self.webcam_enabled_box.isChecked()
        self.settings.auto_detect_game = self.auto_detect_box.isChecked()
        self.settings.riot_api_enabled = self.riot_enabled_box.isChecked()
        self.settings.riot_api_key = self.riot_key_edit.text()
        self.settings.use_biraffe2_svm = self.use_biraffe2_svm_box.isChecked()
        self.settings.use_biraffe2_knn = self.use_biraffe2_knn_box.isChecked()
        self.settings.use_biraffe2_rf = self.use_biraffe2_rf_box.isChecked()
        self.settings.use_irshad_rf = self.use_irshad_rf_box.isChecked()
        self.settings.use_biraffe2_mlp = self.use_biraffe2_mlp_box.isChecked()
        self.settings.window_seconds = self.window_spin.value()
        self.settings.overlap_percent = self.overlap_spin.value()
        self.settings.notification_muting_enabled = self.mute_notifications_box.isChecked()
        self.settings.adaptive_cues_enabled = self.adaptive_cues_box.isChecked()
        self.settings.screen_edge_status_enabled = self.edge_status_box.isChecked()

        self.accept()
