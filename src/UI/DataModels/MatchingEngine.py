from PySide6.QtCore import QObject, Signal
from src.UI.ManualMatching.MatchItem import MatchItem


class ClusterData:
    """A pure Python representation of a Cluster's state."""

    def __init__(self, cluster_id: int, doc_keys: list[str]):
        self.cluster_id = cluster_id
        # Store items grouped by column (doc_key)
        self.items: dict[str, list[MatchItem]] = {key: [] for key in doc_keys}
        self.avg_score: float = 0.0
        self.quality: str = "Laag"
        self.is_approved: bool = False
        self.is_excluded: bool = False


class MatchingEngine(QObject):
    # Signals to tell the UI when to redraw
    stateLoaded = Signal()  # Fired when AI data is initially loaded
    clusterUpdated = Signal(int)  # Fired when a specific cluster's math changes
    clusterAdded = Signal(int)  # Fired when a new cluster is created
    clusterRemoved = Signal(int)  # Fired when a cluster is deleted
    unmatchedUpdated = Signal()  # Fired when the parking lot changes

    def __init__(self):
        super().__init__()
        self.doc_keys: list[str] = []
        self.score_lookup: dict = {}

        self.clusters: dict[int, ClusterData] = {}
        self.unmatched: dict[str, list[MatchItem]] = {}
        self._next_cluster_id = 1

    def load_ai_data(self, doc_keys: list[str], clusters_data: list[dict], lookup: dict, unmatched_dict: dict):
        """Initializes the engine with the raw data from the AI Worker."""
        self.doc_keys = doc_keys
        self.score_lookup = lookup
        self.clusters.clear()

        self.blockSignals(True)

        # Load Unmatched
        self.unmatched = {key: [] for key in self.doc_keys}
        for key in self.doc_keys:
            for raw in unmatched_dict.get(key, []):
                item = MatchItem(raw, raw.get('id', -1), key)
                item.is_parked = True
                self.unmatched[key].append(item)

        # Load Clusters
        self._next_cluster_id = 1
        for cluster_raw in clusters_data:
            self._create_cluster_from_data(cluster_raw)

        self.blockSignals(False)
        self.stateLoaded.emit()

    def create_empty_cluster(self) -> int:
        """Creates a new empty cluster and returns its ID."""
        c_id = self._next_cluster_id
        self.clusters[c_id] = ClusterData(c_id, self.doc_keys)
        self._next_cluster_id += 1
        self.clusterAdded.emit(c_id)
        return c_id

    def delete_cluster(self, cluster_id: int):
        """Deletes a cluster and moves its items to the unmatched pool."""
        if cluster_id not in self.clusters: return

        cluster = self.clusters.pop(cluster_id)

        # Move all items back to unmatched
        for key, items in cluster.items.items():
            for item in items:
                item.is_parked = True
                self.unmatched[key].append(item)

        self.clusterRemoved.emit(cluster_id)
        self.unmatchedUpdated.emit()

    def move_item(self, item: MatchItem, source_cluster_id: int | None, target_cluster_id: int | None):
        """
        The routing hub. Moves an item between clusters or the unmatched pool.
        None = Unmatched Pool.
        """
        key = item.doc_key

        # 1. Remove from Source
        if source_cluster_id is None:
            self.unmatched[key].remove(item)
        else:
            self.clusters[source_cluster_id].items[key].remove(item)

        # 2. Add to Target
        if target_cluster_id is None:
            item.is_parked = True
            item.best_match_name = ""
            self.unmatched[key].append(item)
        else:
            item.is_parked = False
            self.clusters[target_cluster_id].items[key].append(item)

        # 3. Recalculate and Emit
        if source_cluster_id is not None:
            self._recalculate_cluster_math(source_cluster_id)
        else:
            self.unmatchedUpdated.emit()

        if target_cluster_id is not None:
            self._recalculate_cluster_math(target_cluster_id)
        else:
            self.unmatchedUpdated.emit()

    def _recalculate_cluster_math(self, cluster_id: int):
        """The heavy N-document math, extracted directly from your old Cluster.py"""
        cluster = self.clusters[cluster_id]

        # --- 1. CALCULATE TOTALS ---
        totals = {key: {} for key in self.doc_keys}
        for key, items in cluster.items.items():
            for item in items:
                totals[key][item.unit] = totals[key].get(item.unit, 0.0) + item.qty

        cluster_total_score = 0.0
        total_scored_items = 0

        # --- 2. N-DOCUMENT EVALUATION ---
        for i, key_a in enumerate(self.doc_keys):
            for a_item in cluster.items[key_a]:
                best_score = 0.0
                best_name = ""

                # Find highest score against OTHER documents
                for j, key_b in enumerate(self.doc_keys):
                    if i == j: continue
                    for b_item in cluster.items[key_b]:
                        score = self.score_lookup.get((a_item.original_id, b_item.original_id), 0.0)
                        if score == 0.0:
                            score = self.score_lookup.get((b_item.original_id, a_item.original_id), 0.0)
                        if score >= best_score:
                            best_score, best_name = score, b_item.name

                a_item.current_score = best_score
                a_item.best_match_name = best_name
                cluster_total_score += best_score
                total_scored_items += 1

                # Check Units & Quantities
                other_units = set()
                max_other_qty = 0.0
                for j, key_b in enumerate(self.doc_keys):
                    if i == j: continue
                    other_units.update(totals[key_b].keys())
                    other_qty = totals[key_b].get(a_item.unit, 0.0)
                    if other_qty > max_other_qty:
                        max_other_qty = other_qty

                a_item.is_unit_matched = a_item.unit in other_units
                a_qty = totals[key_a].get(a_item.unit, 0.0)

                if max_other_qty > 0:
                    a_item.is_qty_balanced = (abs(a_qty - max_other_qty) / max_other_qty) < 0.02
                else:
                    a_item.is_qty_balanced = (a_qty == 0.0)

        # --- 3. FINALIZE SCORES ---
        cluster.avg_score = (cluster_total_score / total_scored_items) if total_scored_items > 0 else 0.0

        if cluster.avg_score >= 0.70:
            cluster.quality = "Hoog"
        elif cluster.avg_score >= 0.40:
            cluster.quality = "Te controleren"
        else:
            cluster.quality = "Laag"

        # Sort items purely in the data layer
        for key in self.doc_keys:
            cluster.items[key].sort(key=lambda x: x.current_score, reverse=True)

        self.clusterUpdated.emit(cluster_id)

    def _create_cluster_from_data(self, cluster_raw: dict):
        c_id = self.create_empty_cluster()
        legacy_keys = ['contract_a_items', 'contract_b_items']

        for i, key in enumerate(self.doc_keys):
            data_key = legacy_keys[i] if i < 2 and legacy_keys[i] in cluster_raw else key
            for raw in cluster_raw.get(data_key, []):
                item = MatchItem(raw, raw.get('id', -1), key)
                # Directly append so we don't trigger 50 recalculations while loading
                self.clusters[c_id].items[key].append(item)

        self._recalculate_cluster_math(c_id)

    def toggle_exclusion(self, cluster_id: int):
        if cluster_id in self.clusters:
            self.clusters[cluster_id].is_excluded = not self.clusters[cluster_id].is_excluded
            self.clusterUpdated.emit(cluster_id)