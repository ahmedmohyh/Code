"""Settings / configuration dialog with modern card-styled tabs."""

from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
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
from flow_lol.ui.components import CardWidget, Switch
from flow_lol.ui.styles import Colors, Spacing


def _style_primary_button(btn: QPushButton) -> None:
    """Apply a highly-readable primary style directly so it overrides native styles.

    Dialog-button variants can be hard to read with white text on mid-blue, so this
    uses dark text on a light blue background for strong contrast on all displays.
    """
    btn.setStyleSheet(
        f"""
        QPushButton {{
            background: #dbeafe;
            color: #1e3a8a;
            border: 1px solid #93c5fd;
            border-radius: 6px;
            padding: 6px 16px;
            font-weight: 700;
        }}
        QPushButton:hover {{
            background: #bfdbfe;
            border-color: #60a5fa;
        }}
        QPushButton:pressed {{
            background: #93c5fd;
            border-color: #3b82f6;
        }}
        """
    )


def _style_danger_button(btn: QPushButton) -> None:
    """Apply a red danger style for destructive actions."""
    btn.setStyleSheet(
        f"""
        QPushButton {{
            background: {Colors.DANGER};
            color: white;
            border: 1px solid {Colors.DANGER};
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: 700;
        }}
        QPushButton:hover {{
            background: {Colors.DANGER_HOVER};
            border-color: {Colors.DANGER_HOVER};
        }}
        QPushButton:pressed {{
            background: #b91c1c;
            border-color: #b91c1c;
        }}
        """
    )



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
        self._switch_rows: list[tuple[Switch, QLabel]] = []

        tabs.addTab(self._sensors_tab(), "🩺  Sensors")
        tabs.addTab(self._paths_tab(), "💾  Storage")
        tabs.addTab(self._game_tab(), "🎮  Game / Riot")
        tabs.addTab(self._classifier_tab(), "🤖  Classifier")
        tabs.addTab(self._interventions_tab(), "🔔  Interventions")
        tabs.addTab(self._privacy_tab(), "🔒  Privacy")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        # Make the default dialog buttons visually primary/cancel.
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_btn is not None:
            save_btn.setText("💾  Save")
            _style_primary_button(save_btn)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText("✕  Cancel")
            cancel_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {Colors.SURFACE_DIM};
                    color: {Colors.TEXT};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 6px;
                    padding: 6px 16px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {Colors.BORDER};
                    border-color: {Colors.TEXT_MUTED};
                }}
                QPushButton:pressed {{
                    background: #d1d5db;
                    border-color: #9ca3af;
                }}
                """
            )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(Spacing.LG)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    def _make_switch(self, label: str, checked: bool) -> tuple[QWidget, Switch]:
        """Return a row widget containing a label + toggle switch."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(Spacing.MD)
        lbl = QLabel(label)
        lbl.setWordWrap(True)
        switch = Switch(checked=checked)
        row_layout.addWidget(lbl, stretch=1)
        row_layout.addWidget(switch)
        return row, switch

    def _make_model_switch(
        self,
        icon: str,
        title: str,
        subtitle: str,
        checked: bool,
    ) -> tuple[QWidget, Switch]:
        """Return a model row with icon, title/subtitle and a toggle switch."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(Spacing.MD)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 20px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        title_lbl = QLabel(f"<b>{title}</b>")
        title_lbl.setWordWrap(True)
        sub_lbl = QLabel(subtitle)
        sub_lbl.setWordWrap(True)
        sub_lbl.setProperty("role", "muted")
        text_layout.addWidget(title_lbl)
        text_layout.addWidget(sub_lbl)

        switch = Switch(checked=checked)
        row_layout.addWidget(icon_lbl)
        row_layout.addLayout(text_layout, stretch=1)
        row_layout.addWidget(switch)
        return row, switch

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------

    def _sensors_tab(self) -> QWidget:
        card = CardWidget("Sensors")
        form = QFormLayout()
        form.setSpacing(Spacing.MD)

        use_h10_row, self.use_h10_switch = self._make_switch(
            "Use Polar H10 chest belt (ECG)", self.settings.use_h10
        )
        form.addRow(use_h10_row)

        h10_row = QHBoxLayout()
        h10_row.setSpacing(Spacing.SM)
        self.h10_address_edit = QLineEdit(self.settings.h10_address)
        self.h10_address_edit.setPlaceholderText("Scan to set paired MAC address")
        self.h10_address_edit.setReadOnly(True)
        h10_row.addWidget(self.h10_address_edit)

        scan_btn = QPushButton("🔍  Scan...")
        _style_primary_button(scan_btn)
        scan_btn.setToolTip("Search for nearby Polar H10 devices")
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
        ecg_btn = QPushButton("📂  Browse")
        ecg_btn.setToolTip("Choose the ECG save folder")
        ecg_btn.clicked.connect(self._browse_ecg_path)
        ecg_row = QHBoxLayout()
        ecg_row.setSpacing(Spacing.SM)
        ecg_row.addWidget(self.ecg_path_edit)
        ecg_row.addWidget(ecg_btn)
        form.addRow("ECG save folder:", ecg_row)

        self.webcam_path_edit = QLineEdit(self.settings.webcam_save_path)
        self.webcam_path_edit.setReadOnly(True)
        webcam_btn = QPushButton("📂  Browse")
        webcam_btn.setToolTip("Choose the webcam save folder")
        webcam_btn.clicked.connect(self._browse_webcam_path)
        webcam_row = QHBoxLayout()
        webcam_row.setSpacing(Spacing.SM)
        webcam_row.addWidget(self.webcam_path_edit)
        webcam_row.addWidget(webcam_btn)
        form.addRow("Webcam save folder:", webcam_row)

        self.snapshot_path_edit = QLineEdit(self.settings.snapshot_save_path)
        self.snapshot_path_edit.setReadOnly(True)
        snapshot_btn = QPushButton("📂  Browse")
        snapshot_btn.setToolTip("Choose the snapshot save folder")
        snapshot_btn.clicked.connect(self._browse_snapshot_path)
        snapshot_row = QHBoxLayout()
        snapshot_row.setSpacing(Spacing.SM)
        snapshot_row.addWidget(self.snapshot_path_edit)
        snapshot_row.addWidget(snapshot_btn)
        form.addRow("Snapshot save folder:", snapshot_row)

        self.logs_path_edit = QLineEdit(self.settings.logs_save_path)
        self.logs_path_edit.setReadOnly(True)
        logs_btn = QPushButton("📂  Browse")
        logs_btn.setToolTip("Choose the logs save folder")
        logs_btn.clicked.connect(self._browse_logs_path)
        logs_row = QHBoxLayout()
        logs_row.setSpacing(Spacing.SM)
        logs_row.addWidget(self.logs_path_edit)
        logs_row.addWidget(logs_btn)
        form.addRow("Logs save folder:", logs_row)

        self.db_path_edit = QLineEdit(self.settings.db_path)
        self.db_path_edit.setReadOnly(True)
        db_btn = QPushButton("📂  Browse")
        db_btn.setToolTip("Choose the SQLite database file")
        db_btn.clicked.connect(self._browse_db_path)
        db_row = QHBoxLayout()
        db_row.setSpacing(Spacing.SM)
        db_row.addWidget(self.db_path_edit)
        db_row.addWidget(db_btn)
        form.addRow("Database path:", db_row)

        self.replay_path_edit = QLineEdit(self.settings.replay_save_path)
        self.replay_path_edit.setReadOnly(True)
        replay_btn = QPushButton("📂  Browse")
        replay_btn.setToolTip("Choose the League of Legends replay folder")
        replay_btn.clicked.connect(self._browse_replay_path)
        replay_row = QHBoxLayout()
        replay_row.setSpacing(Spacing.SM)
        replay_row.addWidget(self.replay_path_edit)
        replay_row.addWidget(replay_btn)
        form.addRow("LoL replay folder:", replay_row)

        webcam_enabled_row, self.webcam_enabled_switch = self._make_switch(
            "Record webcam during sessions", self.settings.webcam_enabled
        )
        form.addRow(webcam_enabled_row)

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

        auto_detect_row, self.auto_detect_switch = self._make_switch(
            "Auto-detect LoL match start/stop", self.settings.auto_detect_game
        )
        form.addRow(auto_detect_row)

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

        riot_enabled_row, self.riot_enabled_switch = self._make_switch(
            "Enable Riot Games API (requires API key)", self.settings.riot_api_enabled
        )
        self.riot_enabled_switch.setEnabled(False)
        riot_layout.addRow(riot_enabled_row)

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
            "Up to nine ECG-only models vote with a hard majority. "
            "Enable an odd number so the vote always has a winner. "
            "<b>Tip:</b> if a model always votes the same way, it learned a strong bias from the "
            "training data. Disable it and rely on the better-calibrated models."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        layout.addWidget(intro)

        legend = QLabel(
            "<b>Legend:</b> SVM = Support Vector Machine; RF = RandomForest; kNN = k-Nearest Neighbors; "
            "LR = LogisticRegression; MLP = Multi-Layer Perceptron; LSTM = Long Short-Term Memory; "
            "CNN1D = 1-D Convolutional Neural Network; XGB = Extreme Gradient Boosting."
        )
        legend.setWordWrap(True)
        legend.setProperty("role", "muted")
        layout.addWidget(legend)

        models = [
            (
                "🟦",
                "BIRAFFE2 SVM (AUC 0.790)",
                "Support Vector Machine — best overall AUC in the pool. "
                "Good default: finds a boundary between flow and no-flow feature clouds.",
                "use_biraffe2_svm",
            ),
            (
                "🔍",
                "BIRAFFE2 kNN (AUC 0.761)",
                "k-Nearest Neighbors — decides by similarity to stored training windows. "
                "Useful when flow has very characteristic local feature patterns.",
                "use_biraffe2_knn",
            ),
            (
                "🌲",
                "BIRAFFE2 RandomForest (AUC 0.725)",
                "RandomForest — ensemble of decision trees. Robust to noise and gives feature importance. "
                "A safe general-purpose choice.",
                "use_biraffe2_rf",
            ),
            (
                "🌐",
                "Irshad RandomForest (AUC 0.692)",
                "RandomForest trained on the Irshad/PhySF ECG-only dataset. "
                "Lower AUC but adds cross-dataset diversity to the vote.",
                "use_irshad_rf",
            ),
            (
                "🧠",
                "BIRAFFE2 MLP deep learning (AUC 0.730)",
                "Multi-Layer Perceptron — small neural network. Captures non-linear feature interactions. "
                "Fast on CPU and complements classical models.",
                "use_biraffe2_mlp",
            ),
            (
                "📈",
                "BIRAFFE2 LogisticRegression",
                "Linear classifier — fast, low memory, easy to interpret. "
                "Best as a simple baseline or when you want a conservative linear boundary.",
                "use_biraffe2_lr",
            ),
            (
                "⚡",
                "BIRAFFE2 XGBoost",
                "Gradient-boosted trees — often the strongest tabular classifier. "
                "Requires the xgboost package to be installed and exported.",
                "use_biraffe2_xgb",
            ),
            (
                "🔄",
                "BIRAFFE2 LSTM deep learning",
                "Long Short-Term Memory network — sequential model. "
                "May help if flow has temporal structure across consecutive windows.",
                "use_biraffe2_lstm",
            ),
            (
                "🌊",
                "BIRAFFE2 CNN1D deep learning",
                "1-D Convolutional Neural Network — looks for local patterns across the feature vector. "
                "Only usable if the exported feature count is divisible by 4.",
                "use_biraffe2_cnn",
            ),
            (
                "📉",
                "Irshad LogisticRegression",
                "Linear model trained on the Irshad/PhySF dataset. "
                "Adds a cross-dataset linear perspective to the vote.",
                "use_irshad_lr",
            ),
            (
                "🧬",
                "Irshad MLP deep learning",
                "Neural network trained on the Irshad/PhySF dataset. "
                "Adds cross-dataset deep-learning diversity to the vote.",
                "use_irshad_mlp",
            ),
        ]

        self._model_switch_map: Dict[str, Switch] = {}
        for icon, title, subtitle, attr in models:
            row, switch = self._make_model_switch(
                icon,
                title,
                subtitle,
                getattr(self.settings, attr),
            )
            self._model_switch_map[attr] = switch
            layout.addWidget(row)

        # Expose the named switches for validation/save.
        self.use_biraffe2_svm_switch = self._model_switch_map["use_biraffe2_svm"]
        self.use_biraffe2_knn_switch = self._model_switch_map["use_biraffe2_knn"]
        self.use_biraffe2_rf_switch = self._model_switch_map["use_biraffe2_rf"]
        self.use_irshad_rf_switch = self._model_switch_map["use_irshad_rf"]
        self.use_biraffe2_mlp_switch = self._model_switch_map["use_biraffe2_mlp"]
        self.use_biraffe2_lr_switch = self._model_switch_map["use_biraffe2_lr"]
        self.use_biraffe2_xgb_switch = self._model_switch_map["use_biraffe2_xgb"]
        self.use_biraffe2_lstm_switch = self._model_switch_map["use_biraffe2_lstm"]
        self.use_biraffe2_cnn_switch = self._model_switch_map["use_biraffe2_cnn"]
        self.use_irshad_lr_switch = self._model_switch_map["use_irshad_lr"]
        self.use_irshad_mlp_switch = self._model_switch_map["use_irshad_mlp"]

        card.content_layout().addLayout(layout)
        return card

    def _interventions_tab(self) -> QWidget:
        card = CardWidget("Interventions")
        layout = QVBoxLayout()
        layout.setSpacing(Spacing.SM)

        intro = QLabel(
            "Only <b>Screen-edge status</b> is implemented. "
            "Notification muting and adaptive cues are planned for Phase 10 and are disabled until then."
        )
        intro.setWordWrap(True)
        intro.setProperty("role", "muted")
        layout.addWidget(intro)

        mute_row, self.mute_notifications_switch = self._make_switch(
            "Mute system notifications during flow (AF-02)",
            self.settings.notification_muting_enabled,
        )
        mute_lbl = mute_row.findChild(QLabel)
        if mute_lbl is not None:
            mute_lbl.setToolTip(
                "Best-effort Windows Do-Not-Disturb toggle while a flow state is detected. "
                "If it has no effect on your Windows build, enable Focus Assist manually."
            )
        layout.addWidget(mute_row)

        cues_row, self.adaptive_cues_switch = self._make_switch(
            "Lower system volume during flow (adaptive audio cue)",
            self.settings.adaptive_cues_enabled,
        )
        cues_lbl = cues_row.findChild(QLabel)
        if cues_lbl is not None:
            cues_lbl.setToolTip(
                "Reduces the Windows master volume while you are in flow, "
                "then restores it when flow ends or the session stops."
            )
        layout.addWidget(cues_row)

        self.volume_spin = QSpinBox()
        self.volume_spin.setRange(0, 100)
        self.volume_spin.setSuffix("%")
        self.volume_spin.setValue(self.settings.adaptive_volume_percent)
        self.volume_spin.setToolTip("Target master volume while in flow")
        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("Flow volume level:"))
        volume_row.addWidget(self.volume_spin)
        volume_row.addStretch()
        layout.addLayout(volume_row)

        edge_row, self.edge_status_switch = self._make_switch(
            "Screen-edge status box (AF-04)",
            self.settings.screen_edge_status_enabled,
        )
        layout.addWidget(edge_row)

        self.edge_monitor_combo = QComboBox()
        self.edge_monitor_combo.addItem("Primary monitor", -1)
        try:
            screens = QApplication.screens()
        except Exception:
            screens = []
        for i, screen in enumerate(screens):
            try:
                geo = screen.availableGeometry()
                self.edge_monitor_combo.addItem(
                    f"Monitor {i + 1}: {geo.width()}x{geo.height()}", i
                )
            except Exception:
                continue
        monitor_index = getattr(self.settings, "screen_edge_status_monitor", -1)
        current_index = self.edge_monitor_combo.findData(monitor_index)
        if current_index < 0:
            current_index = 0
        self.edge_monitor_combo.setCurrentIndex(current_index)
        monitor_row = QHBoxLayout()
        monitor_row.addWidget(QLabel("Edge box monitor:"))
        monitor_row.addWidget(self.edge_monitor_combo, stretch=1)
        layout.addLayout(monitor_row)

        note = QLabel(
            "The edge box is a normal window, so it cannot appear on top of LoL "
            "when LoL is in <b>exclusive fullscreen</b>. Use LoL's "
            "<b>borderless / windowed</b> mode, or place the box on a secondary monitor."
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
            "ECG recordings, webcam videos, logs, and the SQLite database are stored "
            "under the configured storage folders.<br><br>"
            "Clicking <b>Delete all local data</b> removes those files. "
            "League of Legends replays are managed by the client and are not deleted here."
        )
        info.setWordWrap(True)
        info.setProperty("role", "muted")
        layout.addWidget(info)

        self.data_delete_btn = QPushButton("🗑️  Delete all local data...")
        _style_danger_button(self.data_delete_btn)
        self.data_delete_btn.setToolTip(
            "Delete ECG, webcam, log files and the SQLite database after confirmation"
        )
        self.data_delete_btn.clicked.connect(self._delete_all_local_data)
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

    def _browse_snapshot_path(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Select snapshot save folder", self.snapshot_path_edit.text()
        )
        if path:
            self.snapshot_path_edit.setText(path)

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
        if not self.use_h10_switch.isChecked():
            QMessageBox.warning(self, "Invalid sensors", "Enable the Polar H10 sensor.")
            return

        enabled_classifiers = [
            self.use_biraffe2_svm_switch.isChecked(),
            self.use_biraffe2_knn_switch.isChecked(),
            self.use_biraffe2_rf_switch.isChecked(),
            self.use_irshad_rf_switch.isChecked(),
            self.use_biraffe2_mlp_switch.isChecked(),
            self.use_biraffe2_lr_switch.isChecked(),
            self.use_biraffe2_xgb_switch.isChecked(),
            self.use_biraffe2_lstm_switch.isChecked(),
            self.use_biraffe2_cnn_switch.isChecked(),
            self.use_irshad_lr_switch.isChecked(),
            self.use_irshad_mlp_switch.isChecked(),
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

        # Warn if XGBoost is enabled but not installed; this is non-fatal because
        # the app simply skips the missing bundle file.
        if self.use_biraffe2_xgb_switch.isChecked():
            try:
                import xgboost  # noqa: F401
            except ImportError:
                QMessageBox.information(
                    self,
                    "XGBoost not installed",
                    "XGBoost is enabled but not installed. The app will skip it unless you "
                    "install xgboost and export the model bundle.",
                )

        self.settings.use_h10 = self.use_h10_switch.isChecked()
        self.settings.h10_address = self.h10_address_edit.text().strip()
        self.settings.ecg_save_path = self.ecg_path_edit.text()
        self.settings.webcam_save_path = self.webcam_path_edit.text()
        self.settings.snapshot_save_path = self.snapshot_path_edit.text()
        self.settings.logs_save_path = self.logs_path_edit.text()
        self.settings.db_path = self.db_path_edit.text()
        self.settings.replay_save_path = self.replay_path_edit.text()
        self.settings.webcam_enabled = self.webcam_enabled_switch.isChecked()
        self.settings.auto_detect_game = self.auto_detect_switch.isChecked()
        self.settings.riot_api_enabled = self.riot_enabled_switch.isChecked()
        self.settings.riot_api_key = self.riot_key_edit.text()
        self.settings.use_biraffe2_svm = self.use_biraffe2_svm_switch.isChecked()
        self.settings.use_biraffe2_knn = self.use_biraffe2_knn_switch.isChecked()
        self.settings.use_biraffe2_rf = self.use_biraffe2_rf_switch.isChecked()
        self.settings.use_irshad_rf = self.use_irshad_rf_switch.isChecked()
        self.settings.use_biraffe2_mlp = self.use_biraffe2_mlp_switch.isChecked()
        self.settings.use_biraffe2_lr = self.use_biraffe2_lr_switch.isChecked()
        self.settings.use_biraffe2_xgb = self.use_biraffe2_xgb_switch.isChecked()
        self.settings.use_biraffe2_lstm = self.use_biraffe2_lstm_switch.isChecked()
        self.settings.use_biraffe2_cnn = self.use_biraffe2_cnn_switch.isChecked()
        self.settings.use_irshad_lr = self.use_irshad_lr_switch.isChecked()
        self.settings.use_irshad_mlp = self.use_irshad_mlp_switch.isChecked()
        self.settings.window_seconds = self.window_spin.value()
        self.settings.overlap_percent = self.overlap_spin.value()
        self.settings.notification_muting_enabled = self.mute_notifications_switch.isChecked()
        self.settings.adaptive_cues_enabled = self.adaptive_cues_switch.isChecked()
        self.settings.adaptive_volume_percent = self.volume_spin.value()
        self.settings.screen_edge_status_enabled = self.edge_status_switch.isChecked()
        try:
            self.settings.screen_edge_status_monitor = self.edge_monitor_combo.currentData()
        except Exception:
            self.settings.screen_edge_status_monitor = -1

        self.accept()

    def _delete_all_local_data(self) -> None:
        """Delete local ECG, webcam, logs and DB after confirmation."""
        from flow_lol.utils.logging import get_current_log_file

        reply = QMessageBox.question(
            self,
            "Delete all local data?",
            "This will permanently delete:\n"
            "• ECG recordings\n"
            "• Webcam videos and snapshots\n"
            "• Log files (except the currently open log)\n"
            "• SQLite database\n\n"
            "League of Legends replays are not deleted. "
            "Restart the app afterwards so a fresh database is created.\n\n"
            "Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        current_log = get_current_log_file()
        current_log_resolved = current_log.resolve() if current_log else None
        deleted: list[str] = []
        failed: list[str] = []

        def _clear_dir(path: Path) -> None:
            if not path.exists():
                return
            for item in path.iterdir():
                if current_log_resolved and item.resolve() == current_log_resolved:
                    continue
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    deleted.append(str(item))
                except Exception as exc:
                    failed.append(f"{item}: {exc}")

        _clear_dir(Path(self.settings.ecg_save_path))
        _clear_dir(Path(self.settings.webcam_save_path))
        _clear_dir(Path(self.settings.logs_save_path))

        db_path = Path(self.settings.db_path)
        if db_path.exists():
            try:
                db_path.unlink()
                deleted.append(str(db_path))
            except Exception as exc:
                failed.append(f"{db_path}: {exc}")

        summary: list[str] = []
        if deleted:
            summary.append(f"Deleted {len(deleted)} item(s).")
        else:
            summary.append("No items were found to delete.")
        if failed:
            summary.append(
                f"{len(failed)} item(s) could not be deleted because they are in use. "
                "Close the app and delete them manually, then restart."
            )
        summary.append("Restart Flow-LoL to finish cleanup.")

        QMessageBox.information(self, "Local data deleted", "\n".join(summary))
