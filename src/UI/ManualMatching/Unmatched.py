from src.UI.ManualMatching.BaseCluster import BaseCluster
from src.UI.ManualMatching.MatchItem import MatchItem


class Unmatched(BaseCluster):
    def __init__(self, doc_keys: list[str]):
        # Pass the dynamic doc_keys up to BaseCluster so it can build the columns
        super().__init__("Ongekoppelde Items", doc_keys)

        self.setStyleSheet(
            "Unmatched { background-color: #ffffff; border: 2px dashed #b0b0b0; border-radius: 5px; margin: 15px 5px 5px 5px; }")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #555;")

    def update_ui(self, unmatched_items: dict[str, list[MatchItem]]):
        """Receives the pre-sorted unmatched items directly from the Engine and draws them."""
        max_rows = 1

        for key in self.doc_keys:
            # 1. Get the items for this specific column
            items = unmatched_items.get(key, [])

            # 2. Sort them alphabetically
            items.sort(key=lambda x: x.name.lower() if x.name else "")

            # 3. Inject into the dynamically generated UI lists from BaseCluster
            self.lists[key].rebuild_ui(items)

            # 4. Track the longest list to scale the height correctly
            max_rows = max(max_rows, len(items))

        # Expand the parking lot to fit all items without internal scrollbars
        self.adjust_list_heights(max_visible_rows=max_rows)