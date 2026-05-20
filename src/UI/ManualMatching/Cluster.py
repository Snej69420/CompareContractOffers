from PySide6.QtWidgets import QPushButton, QMessageBox, QApplication
from PySide6.QtCore import Qt, Signal, QPoint, QTimer
from PySide6.QtGui import QIcon, QShortcut, QKeySequence, QCursor

from src.UI.Utils import get_asset_path
from src.UI.ManualMatching.BaseCluster import BaseCluster
from src.UI.ManualMatching.ClusterTooltip import ClusterTooltip
from src.UI.DataProcessing.MatchingEngine import ClusterData


class Cluster(BaseCluster):
    clusterRemoved = Signal(int) # Emits (cluster_id) to tell the Engine to delete this cluster
    itemEjected = Signal(object, int) # Emits (MatchItem, cluster_id) when a user clicks the 'X' to park an item
    itemsChanged = Signal(int) # Emits (cluster_id) when a Qt Drag&Drop happens inside this widget
    excludeToggled = Signal(int) # Emits (cluster_id) when a cluster is marked as excluded

    def __init__(self, cluster_id: int, doc_keys: list[str], contractor_names: dict):
        # Pass the dynamic keys up to the BaseCluster
        super().__init__(f"Cluster {cluster_id}", doc_keys)

        self.setObjectName("ClusterWidget")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.cluster_id = cluster_id
        self.is_approved = False
        self.contractor_names = contractor_names

        self.quality_str = "?"
        self.score_val = 0.0
        self.title_display_mode = "all"

        # Smart timer to prevent aggressive tooltip flashing when navigating fast
        self.tooltip_timer = QTimer(self)
        self.tooltip_timer.setSingleShot(True)
        self.tooltip_timer.timeout.connect(self._show_tooltip)

        self.open_icon = QIcon(get_asset_path("assets/package-open.svg"))
        self.closed_icon = QIcon(get_asset_path("assets/package-closed.svg"))
        self.approve_icon = QIcon(get_asset_path("assets/check.svg"))
        self.edit_icon = QIcon(get_asset_path("assets/pencil.svg"))
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
        self.excluded_icon = QIcon(get_asset_path("assets/eye-off.svg"))
        self.included_icon = QIcon(get_asset_path("assets/eye.svg"))

        self.exclude_btn = QPushButton()
        self.exclude_btn.setIcon(self.included_icon)
        self.exclude_btn.setToolTip("Cluster opgenomen in vergelijking")
        self.exclude_btn.setStyleSheet(button_style)
        self.exclude_btn.clicked.connect(lambda: self.excludeToggled.emit(self.cluster_id))

        self.delete_btn = QPushButton()
        self.delete_btn.setIcon(QIcon(get_asset_path("assets/trash.svg")))
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

        self.exclude_shortcut = QShortcut(QKeySequence("I"), self)
        self.exclude_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.exclude_shortcut.activated.connect(lambda: self.excludeToggled.emit(self.cluster_id))

        self.del_shortcut = QShortcut(QKeySequence("Shift+Del"), self)
        self.del_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.del_shortcut.activated.connect(self.request_removal)

        self.backspace_shortcut = QShortcut(QKeySequence("Shift+Backspace"), self)
        self.backspace_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.backspace_shortcut.activated.connect(self.request_removal)

        self.confirm_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        self.confirm_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.confirm_shortcut.activated.connect(self.toggle_approve)

        self.enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Enter), self)
        self.enter_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.enter_shortcut.activated.connect(self.toggle_approve)

        self.tooltip_popup = ClusterTooltip(contractor_names, self)

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
        self.quality_str = cluster_data.quality
        self.score_val = cluster_data.avg_score

        # Rebuild the lists based purely on the Engine's sorting/data
        for key in self.doc_keys:
            self.lists[key].rebuild_ui(cluster_data.items[key])
        self.refresh_title()

        if cluster_data.is_excluded:
            self.exclude_btn.setIcon(self.excluded_icon)
            self.exclude_btn.setToolTip("Cluster niet opgenomen in vergelijking")
        else:
            self.exclude_btn.setIcon(self.included_icon)
            self.exclude_btn.setToolTip("Cluster opgenomen in vergelijking")

        # 3. Scale height dynamically
        max_items = max([len(lst) for lst in cluster_data.items.values()] + [1])
        self.adjust_list_heights(max_visible_rows=min(max_items, 6))

    def _get_first_item_name(self) -> str | None:
        """Returns the first available item name across all lists."""
        for key in self.doc_keys:
            items = self.lists[key].get_items()

            if items:
                return items[0].name

        return None

    def refresh_title(self):
        """Updates the cluster header UI."""

        if self.is_approved:
            first_name = self._get_first_item_name()

            display_name = first_name if first_name else "..."

            self.title_label.setText(
                f"Cluster {self.cluster_id} ({self.score_val:.0%}) | {display_name}"
            )

        else:
            self.title_label.setText(
                f"Cluster {self.cluster_id} | Zekerheid: "
                f"{self.quality_str} ({self.score_val:.0%})"
            )

            self.tooltip_popup.hide()

    def toggle_approve(self):
        self.is_approved = not self.is_approved
        self.refresh_title()

        if self.is_approved:
            self.lists_widget.setVisible(False)
            self.approve_btn.setText("Aanpassen")
            self.approve_btn.setIcon(self.edit_icon)
            self.icon_label.setIcon(self.closed_icon)

            self.setStyleSheet("""
                #ClusterWidget { background-color: #e2f0e5; border: 1px solid #c3e6cb; border-radius: 5px; }
                #ClusterWidget:focus { border: 2px solid #28a745; background-color: #d4edda; outline: none; }
            """)

            self.setFocus()
        else:
            self.lists_widget.setVisible(True)
            self.approve_btn.setText("Bevestigen")
            self.approve_btn.setIcon(self.approve_icon)
            self.icon_label.setIcon(self.open_icon)

            self.setStyleSheet("""
                #ClusterWidget { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; }
                #ClusterWidget:focus { border: 2px solid #007bff; outline: none; }
            """)

            # Tell the parent tab to drop the cursor back into the correct list
            self.requestGlobalNavigation.emit(self, "", "open")

    # ==========================================
    # --- TOOLTIP HANDLING ---
    # ==========================================
    def focusInEvent(self, event):
        super().focusInEvent(event)
        if self.is_approved and event.reason() != Qt.FocusReason.MouseFocusReason:
            self.tooltip_timer.start(100)

    def _show_tooltip(self):
        cluster_width = self.width()
        target_width = int(cluster_width * 0.8)

        self.tooltip_popup.populate(self.doc_keys, self.lists, target_width)
        self.tooltip_popup.adjustSize()

        tooltip_w = self.tooltip_popup.width()
        tooltip_h = self.tooltip_popup.height()

        x_offset = (cluster_width - tooltip_w) // 2
        global_pos = self.mapToGlobal(QPoint(x_offset, 45))

        screen_geo = QApplication.screenAt(QCursor.pos()).availableGeometry()
        if global_pos.y() + tooltip_h > screen_geo.bottom():
            global_pos.setY(self.mapToGlobal(QPoint(0, 0)).y() - tooltip_h - 5)

        self.tooltip_popup.move(global_pos)
        self.tooltip_popup.show()
        self.tooltip_popup.raise_()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)

        self.tooltip_timer.stop()
        self.tooltip_popup.hide()

    def mouseDoubleClickEvent(self, event):
        if self.is_approved:
            self.toggle_approve()
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        """Catches arrow keys when the Cluster is confirmed and focused as a whole block."""
        if self.is_approved:
            if event.key() == Qt.Key.Key_Up:
                self.requestGlobalNavigation.emit(self, "", "up")
                return
            elif event.key() == Qt.Key.Key_Down:
                self.requestGlobalNavigation.emit(self, "", "down")
                return
            elif event.key() == Qt.Key.Key_Left:
                self.requestGlobalNavigation.emit(self, "", "left_from_cluster")
                return
            elif event.key() == Qt.Key.Key_Right:
                self.requestGlobalNavigation.emit(self, "", "right_from_cluster")
                return
        super().keyPressEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)
        if self.is_approved:
            self.tooltip_timer.start(50)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.tooltip_timer.stop()
        self.tooltip_popup.hide()