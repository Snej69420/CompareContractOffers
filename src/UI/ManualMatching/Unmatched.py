from src.UI.ManualMatching.BaseCluster import BaseCluster
from src.UI.ManualMatching.MatchItem import MatchItem


class Unmatched(BaseCluster):
    def __init__(self, doc_keys: list[str], unmatched_dict: dict):
        # Pass the dynamic doc_keys up to BaseCluster so it can build the columns
        super().__init__("Ongekoppelde Items", doc_keys)

        self.setStyleSheet(
            "Unmatched { background-color: #ffffff; border: 2px dashed #b0b0b0; border-radius: 5px; margin: 15px 5px 5px 5px; }")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #555;")

        self._populate(unmatched_dict)

    def on_items_changed(self):
        """Override base drop handler"""
        self.update_parking_lot()

    def _sort_and_rebuild(self, items_dict: dict):
        """Centralized helper to sort items alphabetically and expand height to fit all."""
        max_rows = 1

        for key in self.doc_keys:
            items = items_dict.get(key, [])
            items.sort(key=lambda x: x.name.lower() if x.name else "")

            # Inject into the dynamically generated UI lists from BaseCluster
            self.lists[key].rebuild_ui(items)

            # Track the longest list to scale the height correctly
            max_rows = max(max_rows, len(items))

        # Expand the parking lot to fit all items without internal scrollbars
        self.adjust_list_heights(max_visible_rows=max_rows)

    def _populate(self, unmatched_dict: dict):
        items_dict = {key: [] for key in self.doc_keys}

        for key in self.doc_keys:
            for raw_data in unmatched_dict.get(key, []):
                item = MatchItem(raw_data, raw_data.get('id', -1), key)
                item.is_parked = True
                items_dict[key].append(item)

        self._sort_and_rebuild(items_dict)

    def receive_items(self, new_items: list[MatchItem]):
        # Gather current items across all N columns
        items_dict = {key: self.lists[key].get_items() for key in self.doc_keys}

        for item in new_items:
            item.is_parked = True
            if item.doc_key in items_dict:
                items_dict[item.doc_key].append(item)

        self._sort_and_rebuild(items_dict)

    def update_parking_lot(self):
        # Gather current items across all N columns
        items_dict = {key: self.lists[key].get_items() for key in self.doc_keys}

        for key, items in items_dict.items():
            for item in items:
                item.is_parked = True
                item.best_match_name = ""

        self._sort_and_rebuild(items_dict)