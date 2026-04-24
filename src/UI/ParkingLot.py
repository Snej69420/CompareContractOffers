from src.UI.BaseCluster import BaseClusterWidget
from src.UI.MatchItem import MatchItem

class ParkingLot(BaseClusterWidget):
    def __init__(self, unmatched_a: list, unmatched_b: list):
        super().__init__("⚠️ Ongekoppelde Items (Parking Lot)")

        self.setStyleSheet(
            "ParkingLotWidget { background-color: #ffffff; border: 2px dashed #b0b0b0; border-radius: 5px; margin: 15px 5px 5px 5px; }")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #555;")

        self._populate(unmatched_a, unmatched_b)

    def on_items_changed(self):
        """Override base drop handler"""
        self.update_parking_lot()

    def _populate(self, unmatched_a, unmatched_b):
        items_a, items_b = [], []
        for raw_a in unmatched_a:
            item = MatchItem(raw_a, raw_a.get('id', -1), 'A')
            item.is_parked = True
            items_a.append(item)
        for raw_b in unmatched_b:
            item = MatchItem(raw_b, raw_b.get('id', -1), 'B')
            item.is_parked = True
            items_b.append(item)

        self.list_a.rebuild_ui(items_a)
        self.list_b.rebuild_ui(items_b)
        self.adjust_list_heights(max_visible_rows=8)

    def receive_items(self, new_items: list[MatchItem]):
        items_a = self.list_a.get_items()
        items_b = self.list_b.get_items()

        for item in new_items:
            item.is_parked = True
            if item.side == 'A':
                items_a.append(item)
            else:
                items_b.append(item)

        self.list_a.rebuild_ui(items_a)
        self.list_b.rebuild_ui(items_b)
        self.update_parking_lot()

    def update_parking_lot(self):
        items_a = self.list_a.get_items()
        items_b = self.list_b.get_items()

        for item in items_a + items_b:
            item.is_parked = True
            item.best_match_name = ""

        self.list_a.rebuild_ui(items_a)
        self.list_b.rebuild_ui(items_b)

        # Leverage the inherited dynamic height method (give it a bit more room)
        self.adjust_list_heights(max_visible_rows=8)