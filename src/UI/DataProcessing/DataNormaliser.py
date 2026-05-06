def _safe_float(val) -> float:
    try:
        if isinstance(val, str): val = val.replace(',', '.')
        return float(val)
    except (ValueError, TypeError):
        return 0.0


class NormalisedItem:
    """A virtual item to fill empty slots without crashing the data models."""

    def __init__(self, name, qty, unit, ep, is_missing=False, is_unmatched_blank=False):
        self.name = name
        self.qty = qty
        self.unit = unit
        self.is_missing = is_missing
        self.is_unmatched_blank = is_unmatched_blank
        self.raw_data = {'Eenheidsprijs': ep}


class DataNormaliser:
    def __init__(self, contract_keys: list[str]):
        self.contract_keys = contract_keys

    def normalize(self, clusters: list[dict], unmatched: list) -> tuple[list[dict], list[dict]]:
        norm_clusters = []

        # --- 1. NORMALIZE CLUSTERS ---
        for cluster in clusters:
            is_excluded = cluster.get('is_excluded', False)
            items_dict = cluster.get('items', cluster)

            # Deep copy the lists to avoid mutating UI state
            new_items = {k: list(items_dict.get(k, [])) for k in self.contract_keys}
            all_present = [i for k in self.contract_keys for i in new_items[k]]

            if not all_present:
                norm_clusters.append({'id': cluster.get('id', -1), 'is_excluded': is_excluded, 'items': new_items})
                continue

            master_name = all_present[0].name
            master_unit = all_present[0].unit

            # Calculate Averages (Only for active clusters)
            if not is_excluded:
                stats = {}
                for k in self.contract_keys:
                    if new_items[k]:
                        qty = sum(_safe_float(i.qty) for i in new_items[k])
                        tot = sum(
                            _safe_float(i.qty) * _safe_float(i.raw_data.get('Eenheidsprijs', 0)) for i in new_items[k])
                        stats[k] = (qty, tot)

                avg_qty = sum(s[0] for s in stats.values()) / len(stats) if stats else 0.0
                avg_tot = sum(s[1] for s in stats.values()) / len(stats) if stats else 0.0
                avg_ep = avg_tot / avg_qty if avg_qty > 0 else 0.0

                # Fill empty contractor slots with Virtual Items
                for k in self.contract_keys:
                    if not new_items[k]:
                        dummy = NormalisedItem(f"[MISSING] {master_name}", avg_qty, master_unit, avg_ep,
                                               is_missing=True)
                        new_items[k].append(dummy)

            norm_clusters.append({
                'id': cluster.get('id', -1),
                'is_excluded': is_excluded,
                'items': new_items
            })

        # --- 2. NORMALIZE UNMATCHED ---
        # Wrap each unmatched item into a "pseudo-cluster" so generators treat them normally
        norm_unmatched = []
        for item in unmatched:
            pseudo = {k: [] for k in self.contract_keys}
            pseudo[item.doc_key].append(item)

            for k in self.contract_keys:
                if k != item.doc_key:
                    pseudo[k].append(NormalisedItem("", "", "", 0.0, is_missing=True, is_unmatched_blank=True))

            norm_unmatched.append(pseudo)

        return norm_clusters, norm_unmatched