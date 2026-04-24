class MatchItem:
    def __init__(self, raw_data: dict, original_id: int, side: str):
        self.raw_data = raw_data
        self.name = raw_data.get('Naam', 'Onbekend')

        # Clean quantities and units
        try:
            self.qty = float(raw_data.get('Aantal', 0))
        except (ValueError, TypeError):
            self.qty = 0.0

        self.unit = raw_data.get('unit', '')

        self.original_id = original_id
        self.side = side
        self.current_score = 0.0
        self.best_match_name = ""

        self.is_qty_balanced = False
        self.is_unit_matched = False
        self.is_parked = False

    def display_text(self):
        return f"{self.name} ({self.qty} {self.unit})"