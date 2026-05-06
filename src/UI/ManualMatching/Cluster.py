from pathlib import Path
from PySide6.QtWidgets import QPushButton, QMessageBox
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QShortcut, QKeySequence

from src.UI.ManualMatching.BaseCluster import BaseCluster
from src.UI.DataProcessing.MatchingEngine import ClusterData  # Import our new data model


class Cluster(BaseCluster):
    clusterRemoved = Signal(int) # Emits (cluster_id) to tell the Engine to delete this cluster
    itemEjected = Signal(object, int) # Emits (MatchItem, cluster_id) when a user clicks the 'X' to park an item
    itemsChanged = Signal(int) # Emits (cluster_id) when a Qt Drag&Drop happens inside this widget
    excludeToggled = Signal(int) # Emits (cluster_id) when a cluster is marked as excluded

    def __init__(self, cluster_id: int, doc_keys: list[str]):
        # Pass the dynamic keys up to the BaseCluster
        super().__init__(f"Cluster {cluster_id}", doc_keys)

        self.cluster_id = cluster_id
        self.is_approved = False

        icon_dir = Path(__file__).parent.parent.parent.parent / "assets"
        self.open_icon = QIcon(str(icon_dir / "package-open.svg"))
        self.closed_icon = QIcon(str(icon_dir / "package-closed.svg"))
        self.approve_icon = QIcon(str(icon_dir / "check.svg"))
        self.edit_icon = QIcon(str(icon_dir / "pencil.svg"))
        self.icon_label.setIcon(self.open_icon)

        self.setStyleSheet(
            "ClusterWidget { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; }")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: black;")

        button_style = """
            QPushButton {
                border-radius: 3px;
                padding: 5px;
                min-height: 24px;  /* Forces consistent height */
            }
        """

        # Header buttons
        self.excluded_icon = QIcon(str(icon_dir / "eye-off.svg"))
        self.included_icon = QIcon(str(icon_dir / "eye.svg"))

        # 2. Update the exclude_btn
        self.exclude_btn = QPushButton()
        self.exclude_btn.setIcon(self.included_icon)
        self.exclude_btn.setToolTip("Item opgenomen in vergelijking")
        self.exclude_btn.setStyleSheet(button_style)
        self.exclude_btn.clicked.connect(lambda: self.excludeToggled.emit(self.cluster_id))

        self.delete_btn = QPushButton()
        self.delete_btn.setIcon(QIcon(str(icon_dir / "trash.svg")))
        self.delete_btn.setStyleSheet(button_style)
        self.delete_btn.setToolTip("Cluster verwijderen")
        self.delete_btn.clicked.connect(self.request_removal)

        self.approve_btn = QPushButton("Bevestigen")
        self.approve_btn.setIcon(self.approve_icon)
        self.approve_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.approve_btn.clicked.connect(self.toggle_approve)
        self.approve_btn.setStyleSheet(button_style)

        self.header_layout.addWidget(self.exclude_btn)
        self.header_layout.addWidget(self.delete_btn)
        self.header_layout.addWidget(self.approve_btn)

        # Wire up ejection logic from the dynamically generated lists
        for lst in self.lists.values():
            lst.itemEjected.connect(self._handle_eject)

        self.del_shortcut = QShortcut(QKeySequence("Shift+Del"), self)
        self.del_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.del_shortcut.activated.connect(self.request_removal)

        self.backspace_shortcut = QShortcut(QKeySequence("Shift+Backspace"), self)
        self.backspace_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.backspace_shortcut.activated.connect(self.request_removal)

    def on_items_changed(self):
        """Overrides the BaseCluster drop handler to alert the parent that a drop happened."""
        self.itemsChanged.emit(self.cluster_id)

    def _handle_eject(self, match_item):
        """Alerts the parent that an item needs to go to the Parking Lot."""
        self.itemEjected.emit(match_item, self.cluster_id)

    def request_removal(self):
        """Alerts the parent that this cluster should be deleted."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle('Cluster Verwijderen')
        msg_box.setText(
            'Weet je zeker dat je deze cluster wilt verwijderen?'
            '\nDe items zullen toegevoegd worden aan de lijst met ongekoppelde items')
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        msg_box.setButtonText(QMessageBox.StandardButton.Yes, "Ja")
        msg_box.setButtonText(QMessageBox.StandardButton.No, "Nee")

        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            # We don't need to gather items anymore. The Engine knows what's in here!
            self.clusterRemoved.emit(self.cluster_id)

    def update_ui(self, cluster_data: ClusterData):
        """Receives pre-calculated data from the Engine and simply renders it."""

        # 1. Update Title with calculated scores
        self.title_label.setText(
            f"Cluster {self.cluster_id} | Zekerheid: {cluster_data.quality} ({cluster_data.avg_score:.0%})")

        # 2. Rebuild the lists based purely on the Engine's sorting/data
        for key in self.doc_keys:
            self.lists[key].rebuild_ui(cluster_data.items[key])

        if cluster_data.is_excluded:
            self.exclude_btn.setIcon(self.excluded_icon)
            self.exclude_btn.setToolTip("Item niet opgenomen in vergelijking")
        else:
            self.exclude_btn.setIcon(self.included_icon)
            self.exclude_btn.setToolTip("Item opgenomen in vergelijking")

        # 3. Scale height dynamically
        max_items = max([len(lst) for lst in cluster_data.items.values()] + [1])
        self.adjust_list_heights(max_visible_rows=min(max_items, 6))

    def toggle_approve(self):
        """Pure UI State - no data changes here."""
        self.is_approved = not self.is_approved
        if self.is_approved:
            self.lists_widget.setVisible(False)
            self.approve_btn.setText("Aanpassen")
            self.approve_btn.setIcon(self.edit_icon)
            self.icon_label.setIcon(self.closed_icon)
            self.setStyleSheet(
                "ClusterWidget { background-color: #e2f0e5; border: 1px solid #c3e6cb; border-radius: 5px; }")
        else:
            self.lists_widget.setVisible(True)
            self.approve_btn.setText("Bevestigen")
            self.approve_btn.setIcon(self.approve_icon)
            self.icon_label.setIcon(self.open_icon)
            self.setStyleSheet(
                "ClusterWidget { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; }")

    def mouseDoubleClickEvent(self, event):
        if self.is_approved:
            self.toggle_approve()
        super().mouseDoubleClickEvent(event)