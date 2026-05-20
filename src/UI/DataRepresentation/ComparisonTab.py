from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import QShortcut, QKeySequence, QIcon

from src.UI.Utils import get_asset_path
from src.UI.ManualMatching.Cluster import Cluster
from src.UI.ManualMatching.Unmatched import Unmatched
from src.UI.DataProcessing.MatchingEngine import MatchingEngine


class ComparisonTab(QWidget):
    stateChanged = Signal()

    def __init__(self):
        super().__init__()
        self.engine = MatchingEngine()
        self._wire_engine_signals()

        self.cluster_widgets = {}
        self.parking_lot_widget = None
        self.active_column_key = ""

        # --- CAROUSEL STATE ---
        self.current_start_index = 0
        self.visible_columns_count = 2
        self.ideal_column_width = 512

        # --- SETUP UI LAYOUT ---
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # --- NAVIGATION BUTTON STYLING ---
        nav_btn_style = """
            QPushButton {
                background-color: #f0f0f0;
                border: none;
                border-radius: 10px; /* Half of the 24px width to make a pill shape */
            }
            QPushButton:hover {
                background-color: #dcdcdc;
            }
            QPushButton:disabled {
                background-color: transparent;
            }
        """

        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(QIcon(get_asset_path("assets/chevron-left.svg")))
        self.prev_btn.setIconSize(QSize(20, 20))
        self.prev_btn.setFixedSize(20, 40)
        self.prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.prev_btn.setStyleSheet(nav_btn_style)
        self.prev_btn.clicked.connect(self.page_prev)

        self.next_btn = QPushButton()
        self.next_btn.setIcon(QIcon(get_asset_path("assets/chevron-right.svg")))
        self.next_btn.setIconSize(QSize(20, 20))
        self.next_btn.setFixedSize(20, 40)
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setStyleSheet(nav_btn_style)
        self.next_btn.clicked.connect(self.page_next)

        # --- WORKSPACE CONTAINER (Headers + Scroll Area) ---
        self.workspace_layout = QVBoxLayout()
        self.workspace_layout.setContentsMargins(0, 10, 0, 0)

        # Headers
        self.column_headers_layout = QHBoxLayout()
        self.column_headers_layout.setContentsMargins(0, 0, 0, 0)
        self.column_headers_layout.setSpacing(10)
        self.workspace_layout.addLayout(self.column_headers_layout)

        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.cluster_container = QWidget()
        self.cluster_layout = QVBoxLayout(self.cluster_container)
        self.cluster_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cluster_layout.setContentsMargins(0, 10, 0, 0)
        self.cluster_layout.setSpacing(10)

        self.scroll_area.setWidget(self.cluster_container)
        self.workspace_layout.addWidget(self.scroll_area)

        # --- CAROUSEL LAYOUT ---
        # [ Prev Btn ] [ Workspace (Headers + Clusters) ] [ Next Btn ]
        self.carousel_layout = QHBoxLayout()
        self.carousel_layout.setContentsMargins(5, 0, 5, 0)
        self.carousel_layout.setSpacing(5)

        self.carousel_layout.addWidget(self.prev_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
        self.carousel_layout.addLayout(self.workspace_layout, stretch=1)
        self.carousel_layout.addWidget(self.next_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.layout.addLayout(self.carousel_layout)

        # --- BOTTOM ACTION ROW ---
        self.add_cluster_btn = QPushButton("Nieuwe cluster toevoegen")
        self.add_cluster_btn.setEnabled(False)
        self.add_cluster_btn.setStyleSheet(
            "background-color: #007bff; color: white; font-weight: bold; border-radius: 5px; padding: 10px; margin: 10px 15px;"
        )
        self.add_cluster_btn.clicked.connect(self.engine.create_empty_cluster)
        self.layout.addWidget(self.add_cluster_btn)

        # Shortcuts
        self.new_cluster_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        self.new_cluster_shortcut.activated.connect(self.engine.create_empty_cluster)

    def _wire_engine_signals(self):
        self.engine.stateLoaded.connect(self._build_entire_ui)
        self.engine.clusterAdded.connect(self._create_cluster_widget)
        self.engine.clusterRemoved.connect(self._remove_cluster_widget)
        self.engine.clusterUpdated.connect(self._update_cluster_widget)
        self.engine.unmatchedUpdated.connect(self._update_parking_lot_widget)

    # ==========================================
    # --- DATA INGRESS & EGRESS ---
    # ==========================================
    def populate_from_ai(self, doc_keys: list[str], clusters: list[dict], lookup: dict, unmatched_dict: dict):
        self.engine.load_ai_data(doc_keys, clusters, lookup, unmatched_dict)

    def gather_current_state(self):
        clusters_data = []
        for c_id, c_data in self.engine.clusters.items():
            clusters_data.append({
                'items': c_data.items,
                'is_excluded': c_data.is_excluded
            })

        unmatched_items = []
        for items in self.engine.unmatched.values():
            unmatched_items.extend(items)

        return clusters_data, unmatched_items

    # ==========================================
    # --- CAROUSEL NAVIGATION LOGIC ---
    # ==========================================
    def page_prev(self):
        if self.current_start_index > 0:
            self.current_start_index -= 1
            self.update_carousel_view()

    def page_next(self):
        if self.current_start_index < len(self.engine.doc_keys) - self.visible_columns_count:
            self.current_start_index += 1
            self.update_carousel_view()

    def update_carousel_view(self):
        """Hides and shows elements based on the current window of keys."""
        if not self.engine.doc_keys:
            return

        # Determine which keys are active right now
        end_idx = self.current_start_index + self.visible_columns_count
        visible_keys = self.engine.doc_keys[self.current_start_index: end_idx]

        # 1. Update Navigation Button States
        self.prev_btn.setEnabled(self.current_start_index > 0)
        self.next_btn.setEnabled(end_idx < len(self.engine.doc_keys))

        # 2. Update Header Visibility
        for i in range(self.column_headers_layout.count()):
            widget = self.column_headers_layout.itemAt(i).widget()
            if widget:
                key = self.engine.doc_keys[i]
                widget.setVisible(key in visible_keys)

        # 3. Update Cluster and Parking Lot Visibility
        for widget in self.cluster_widgets.values():
            widget.set_visible_columns(visible_keys)

        if self.parking_lot_widget:
            self.parking_lot_widget.set_visible_columns(visible_keys)

    # ==========================================
    # --- UI RENDERING METHODS ---
    # ==========================================
    def _build_entire_ui(self):
        self.add_cluster_btn.setEnabled(True)
        self.current_start_index = 0  # Reset carousel on new load

        # 1. Clear Headers
        while self.column_headers_layout.count():
            item = self.column_headers_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        # 2. Rebuild Headers
        for key in self.engine.doc_keys:
            lbl = QLabel(key)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                "font-weight: bold; font-size: 14px; padding: 6px; background-color: #d1d9e6; border-radius: 4px; color: #333;")
            self.column_headers_layout.addWidget(lbl)

        # 3. Clear existing Clusters safely
        for widget in self.cluster_widgets.values():
            widget.setParent(None)
            widget.deleteLater()
        self.cluster_widgets.clear()

        if self.parking_lot_widget:
            self.parking_lot_widget.setParent(None)
            self.parking_lot_widget.deleteLater()
            self.parking_lot_widget = None

        # 4. Build new Clusters from Engine state
        for c_id in self.engine.clusters.keys():
            self._create_cluster_widget(c_id)

        # 5. Build Parking Lot
        self.parking_lot_widget = Unmatched(self.engine.doc_keys)
        self.cluster_layout.addWidget(self.parking_lot_widget)
        self._update_parking_lot_widget()

        self.parking_lot_widget.requestNeighborMove.connect(self.handle_neighbor_move)
        self.parking_lot_widget.requestGlobalNavigation.connect(self.handle_global_navigation)
        self.parking_lot_widget.requestDragRoute.connect(self.handle_drag_drop)
        self.parking_lot_widget.requestScrollTo.connect(self.handle_scroll_request)

        if self.engine.doc_keys:
            self.active_column_key = self.engine.doc_keys[0]

        self.update_carousel_view()
        self.stateChanged.emit()

        QTimer.singleShot(0, self._recalculate_column_count)

    def _create_cluster_widget(self, cluster_id: int):
        widget = Cluster(cluster_id, self.engine.doc_keys)

        widget.clusterRemoved.connect(self.engine.delete_cluster)
        widget.itemEjected.connect(lambda item, c_id: self.engine.move_item(item, c_id, None))
        widget.excludeToggled.connect(self.engine.toggle_exclusion)

        widget.requestNeighborMove.connect(self.handle_neighbor_move)
        widget.requestGlobalNavigation.connect(self.handle_global_navigation)
        widget.requestDragRoute.connect(self.handle_drag_drop)
        widget.requestScrollTo.connect(self.handle_scroll_request)

        if self.parking_lot_widget:
            idx = self.cluster_layout.indexOf(self.parking_lot_widget)
            self.cluster_layout.insertWidget(idx, widget)
        else:
            self.cluster_layout.addWidget(widget)

        self.cluster_widgets[cluster_id] = widget
        self._update_cluster_widget(cluster_id)

        # Ensure new cluster respects the current carousel window
        self.update_carousel_view()

    def _remove_cluster_widget(self, cluster_id: int):
        if cluster_id in self.cluster_widgets:
            widget = self.cluster_widgets.pop(cluster_id)
            self.cluster_layout.removeWidget(widget)
            widget.deleteLater()
            self.stateChanged.emit()

    def _update_cluster_widget(self, cluster_id: int):
        if cluster_id in self.cluster_widgets and cluster_id in self.engine.clusters:
            data = self.engine.clusters[cluster_id]
            self.cluster_widgets[cluster_id].update_ui(data)
            self.stateChanged.emit()

    def _update_parking_lot_widget(self):
        if self.parking_lot_widget:
            self.parking_lot_widget.update_ui(self.engine.unmatched)
        self.stateChanged.emit()

    def resizeEvent(self, event):
        """Dynamically calculates how many columns to show based on window width."""
        super().resizeEvent(event)
        self._recalculate_column_count()

    def _recalculate_column_count(self):
        """The actual math for dynamic columns, usable anywhere."""
        if not hasattr(self, 'engine') or not self.engine.doc_keys:
            return

        available_width = self.scroll_area.viewport().width()

        if available_width > 0:
            calculated_columns = available_width // self.ideal_column_width
            new_count = max(2, min(calculated_columns, 5))
            new_count = min(new_count, len(self.engine.doc_keys))

            if new_count != self.visible_columns_count:
                self.visible_columns_count = new_count

                max_start_idx = max(0, len(self.engine.doc_keys) - self.visible_columns_count)
                self.current_start_index = min(self.current_start_index, max_start_idx)

                self.update_carousel_view()

    # ==========================================
    # --- KEYBOARD SHORTCUT ROUTING ---
    # ==========================================
    def handle_neighbor_move(self, source_widget, match_items, direction):
        idx = self.cluster_layout.indexOf(source_widget)

        target_widget = None
        step = -1 if direction == "up" else 1
        current_search_idx = idx + step

        while 0 <= current_search_idx < self.cluster_layout.count():
            potential_widget = self.cluster_layout.itemAt(current_search_idx).widget()

            # Skip the "Add Cluster" button
            if isinstance(potential_widget, QPushButton):
                current_search_idx += step
                continue

            # Check if it's an approved cluster
            if isinstance(potential_widget, Cluster) and potential_widget.is_approved:
                current_search_idx += step
                continue

            # If we found a non-approved cluster or the Unmatched/ParkingLot, we stop
            target_widget = potential_widget
            break

        if target_widget:
            source_id = getattr(source_widget, 'cluster_id', None)
            target_id = getattr(target_widget, 'cluster_id', None)

            # Loop through all selected items and move them
            for match_item in match_items:
                self.engine.move_item(match_item, source_id, target_id)

            # Focus the first item in the moved batch
            if hasattr(target_widget, 'select_items') and match_items:
                target_widget.select_items(match_items)

    def handle_global_navigation(self, source_widget, key, direction):
        # 1. Update Column Memory (Fallback to memory if the signal sent "" from an approved cluster)
        if key:
            self.active_column_key = key
        else:
            key = self.active_column_key

        # 2. Handle Re-Opening a Cluster
        if direction == "open":
            if key and key in source_widget.lists:
                source_widget.lists[key].setFocus()
            return

        # 3. Handle Horizontal Navigation
        if direction in ("left", "right", "left_from_cluster", "right_from_cluster"):
            # If the user is on a closed cluster and presses left/right, shift the memory manually
            if "from_cluster" in direction:
                idx = self.engine.doc_keys.index(key)
                if direction.startswith("left") and idx > 0:
                    key = self.engine.doc_keys[idx - 1]
                elif direction.startswith("right") and idx < len(self.engine.doc_keys) - 1:
                    key = self.engine.doc_keys[idx + 1]
                self.active_column_key = key

            # Carousel Auto-Scrolling Logic
            target_idx = self.engine.doc_keys.index(key)
            visible_end = self.current_start_index + self.visible_columns_count - 1

            # Shift window left if we moved before the current start
            if target_idx < self.current_start_index:
                self.current_start_index = target_idx
                self.update_carousel_view()

            # Shift window right if we moved past the current end
            elif target_idx > visible_end:
                self.current_start_index = target_idx - self.visible_columns_count + 1
                self.update_carousel_view()
            return  # Left/Right doesn't move vertically

        # --- VERTICAL NAVIGATION (Jumping between Clusters) ---
        idx = self.cluster_layout.indexOf(source_widget)
        target_idx = idx - 1 if direction == "up" else idx + 1

        if 0 <= target_idx < self.cluster_layout.count():
            target_widget = self.cluster_layout.itemAt(target_idx).widget()

            # Skip over the add Cluster button if it's in the layout
            if isinstance(target_widget, QPushButton):
                target_idx = target_idx - 1 if direction == "up" else target_idx + 1
                if 0 <= target_idx < self.cluster_layout.count():
                    target_widget = self.cluster_layout.itemAt(target_idx).widget()
                else:
                    return

            # approved cluster? => highlight the WHOLE cluster
            if getattr(target_widget, 'is_approved', False):
                target_widget.setFocus()
                self.handle_scroll_request(target_widget)
            else:
                target_list = target_widget.lists[key]
                target_list.setFocus()

                # Keep the cursor at the bottom if moving up, or top if moving down
                if target_list.count() > 0:
                    target_row = target_list.count() - 1 if direction == "up" else 0
                    target_list.setCurrentRow(target_row)

                    # --- NEW: Ensure the newly focused row is visible ---
                    item = target_list.item(target_row)
                    item_widget = target_list.itemWidget(item)
                    if item_widget:
                        self.handle_scroll_request(item_widget)
                    else:
                        self.handle_scroll_request(target_widget)
                else:
                    # If jumping into an empty list, just scroll to the cluster itself
                    self.handle_scroll_request(target_widget)

    def handle_scroll_request(self, target_widget):
        """Forces the QScrollArea to bring the specific widget/row into view."""
        QTimer.singleShot(0, lambda: self.scroll_area.ensureWidgetVisible(target_widget, xmargin=0, ymargin=50))

    def handle_drag_drop(self, match_items, source_list, target_list):
        source_id = None
        target_id = None

        all_clusters = list(self.cluster_widgets.values())
        if self.parking_lot_widget:
            all_clusters.append(self.parking_lot_widget)

        for widget in all_clusters:
            if source_list in widget.lists.values():
                source_id = getattr(widget, 'cluster_id', None)
            if target_list in widget.lists.values():
                target_id = getattr(widget, 'cluster_id', None)

        # Loop through all dragged items and move them
        for match_item in match_items:
            self.engine.move_item(match_item, source_id, target_id)

        # Focus the first item in the moved batch
        for widget in all_clusters:
            if getattr(widget, 'cluster_id', None) == target_id:
                if hasattr(widget, 'focus_on_item') and match_items:
                    widget.focus_on_item(match_items[0])