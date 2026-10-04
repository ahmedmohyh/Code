"""Settings / configuration dialog."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
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


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Flow-LoL Settings")
        self.setMinimumSize(650, 500)

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
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _sensors_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self.use_h10_box = QCheckBox("Use Polar H10 chest belt (ECG)")
        self.use_h10_box.setChecked(self.settings.use_h10)
        form.addRow(self.use_h10_box)

        self.use_verity_box = QCheckBox("Use Polar Verity Sense armband")
        self.use_verity_box.setChecked(self.settings.use_verity)
        form.addRow(self.use_verity_box)

        self.preferred_sensor_combo = QComboBox()
        self.preferred_sensor_combo.addItems(["auto", "h10", "verity"])
        self.preferred_sensor_combo.setCurrentText(self.settings.preferred_sensor)
        form.addRow("Preferred sensor (if both connected):", self.preferred_sensor_combo)

        self.window_spin = QSpinBox()
        self.window_spin.setRange(10, 300)
        self.window_spin.setValue(self.settings.window_seconds)
        form.addRow("Analysis window (seconds):", self.window_spin)

        self.overlap_spin = QSpinBox()
        self.overlap_spin.setRange(0, 90)
        self.overlap_spin.setValue(self.settings.overlap_percent)
        form.addRow("Window overlap (%):", self.overlap_spin)

        return widget

    def _paths_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self.ecg_path_edit = QLineEdit(self.settings.ecg_save_path)
        self.ecg_path_edit.setReadOnly(True)
        ecg_btn = QPushButton("Browse...")
        ecg_btn.clicked.connect(self._browse_ecg_path)
        ecg_row = QHBoxLayout()
        ecg_row.addWidget(self.ecg_path_edit)
        ecg_row.addWidget(ecg_btn)
        form.addRow("ECG save folder:", ecg_row)

        self.webcam_path_edit = QLineEdit(self.settings.webcam_save_path)
        self.webcam_path_edit.setReadOnly(True)
        webcam_btn = QPushButton("Browse...")
        webcam_btn.clicked.connect(self._browse_webcam_path)
        webcam_row = QHBoxLayout()
        webcam_row.addWidget(self.webcam_path_edit)
        webcam_row.addWidget(webcam_btn)
        form.addRow("Webcam save folder:", webcam_row)

        self.webcam_enabled_box = QCheckBox("Record webcam during sessions")
        self.webcam_enabled_box.setChecked(self.settings.webcam_enabled)
        form.addRow(self.webcam_enabled_box)

        return widget

    def _game_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self.auto_detect_box = QCheckBox("Auto-detect LoL match start/stop")
        self.auto_detect_box.setChecked(self.settings.auto_detect_game)
        form.addRow(self.auto_detect_box)

        self.riot_enabled_box = QCheckBox("Enable Riot Games API (requires API key)")
        self.riot_enabled_box.setChecked(self.settings.riot_api_enabled)
        self.riot_enabled_box.setEnabled(False)
        form.addRow(self.riot_enabled_box)

        self.riot_key_edit = QLineEdit(self.settings.riot_api_key)
        self.riot_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.riot_key_edit.setEnabled(False)
        form.addRow("Riot API key:", self.riot_key_edit)

        note = QLabel(
            "Riot API integration is planned but not yet implemented. "
            "Manual start/stop and LoL-client process detection are used first."
        )
        note.setWordWrap(True)
        form.addRow(note)

        return widget

    def _classifier_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        group = QGroupBox("Ensemble members – five ECG-only models, hard majority vote")
        group_layout = QVBoxLayout(group)

        self.use_biraffe2_svm_box = QCheckBox("BIRAFFE2 SVM (AUC 0.790)")
        self.use_biraffe2_svm_box.setChecked(self.settings.use_biraffe2_svm)
        group_layout.addWidget(self.use_biraffe2_svm_box)

        self.use_biraffe2_knn_box = QCheckBox("BIRAFFE2 kNN (AUC 0.761)")
        self.use_biraffe2_knn_box.setChecked(self.settings.use_biraffe2_knn)
        group_layout.addWidget(self.use_biraffe2_knn_box)

        self.use_biraffe2_rf_box = QCheckBox("BIRAFFE2 RandomForest (AUC 0.725)")
        self.use_biraffe2_rf_box.setChecked(self.settings.use_biraffe2_rf)
        group_layout.addWidget(self.use_biraffe2_rf_box)

        self.use_irshad_rf_box = QCheckBox("Irshad RandomForest (AUC 0.692)")
        self.use_irshad_rf_box.setChecked(self.settings.use_irshad_rf)
        group_layout.addWidget(self.use_irshad_rf_box)

        self.use_biraffe2_mlp_box = QCheckBox("BIRAFFE2 MLP deep learning (AUC 0.730)")
        self.use_biraffe2_mlp_box.setChecked(self.settings.use_biraffe2_mlp)
        group_layout.addWidget(self.use_biraffe2_mlp_box)

        form.addRow(group)
        return widget

    def _interventions_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)

        self.mute_notifications_box = QCheckBox("Mute system notifications during flow (Phase 10)")
        self.mute_notifications_box.setChecked(self.settings.notification_muting_enabled)
        self.mute_notifications_box.setEnabled(False)
        form.addRow(self.mute_notifications_box)

        self.adaptive_cues_box = QCheckBox("Adaptive audio / lighting cues (Phase 10)")
        self.adaptive_cues_box.setChecked(self.settings.adaptive_cues_enabled)
        self.adaptive_cues_box.setEnabled(False)
        form.addRow(self.adaptive_cues_box)

        self.edge_status_box = QCheckBox("Screen-edge status only, no in-game overlay (AF-04)")
        self.edge_status_box.setChecked(self.settings.screen_edge_status_enabled)
        form.addRow(self.edge_status_box)

        note = QLabel(
            "Full disturbance-reduction features are planned for Phase 10. "
            "Until then the app avoids in-game overlays."
        )
        note.setWordWrap(True)
        form.addRow(note)

        return widget

    def _privacy_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "All data is processed locally on this PC.\n"
            "ECG recordings, webcam videos, and the SQLite database are stored "
            "under the configured storage folders.\n\n"
            "You can delete your local data from here once the database module is implemented."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.data_delete_btn = QPushButton("Delete all local data...")
        self.data_delete_btn.setEnabled(False)
        layout.addWidget(self.data_delete_btn)
        layout.addStretch()
        return widget

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

    def _validate_and_accept(self) -> None:
        if not (self.use_h10_box.isChecked() or self.use_verity_box.isChecked()):
            QMessageBox.warning(self, "Invalid sensors", "Enable at least one sensor.")
            return
        if not (self.use_biraffe2_svm_box.isChecked() or self.use_biraffe2_knn_box.isChecked()
                or self.use_biraffe2_rf_box.isChecked() or self.use_irshad_rf_box.isChecked()
                or self.use_biraffe2_mlp_box.isChecked()):
            QMessageBox.warning(self, "Invalid classifiers", "Enable at least one classifier.")
            return

        self.settings.use_h10 = self.use_h10_box.isChecked()
        self.settings.use_verity = self.use_verity_box.isChecked()
        self.settings.preferred_sensor = self.preferred_sensor_combo.currentText()
        self.settings.ecg_save_path = self.ecg_path_edit.text()
        self.settings.webcam_save_path = self.webcam_path_edit.text()
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
