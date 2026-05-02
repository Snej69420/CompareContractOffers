import pandas as pd


class ReportGenerator:
    def __init__(self, contract_names: dict[str, str]):
        self.contract_keys = list(contract_names.keys())
        self.contract_names = contract_names
        self.metrics = ['Naam', 'Aantal', 'Eenheid', 'Eenheidsprijs', 'Totaalprijs']

    def _safe_float(self, val) -> float:
        try:
            if isinstance(val, str): val = val.replace(',', '.')
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def generate(self, clusters: list[dict], unmatched: list) -> tuple[pd.DataFrame, pd.DataFrame, list[tuple]]:
        # --- NEW: Calculate grand totals to sort contractors from cheapest to most expensive ---
        contractor_totals = {k: 0.0 for k in self.contract_keys}

        # Sum up prices from all matched clusters
        for cluster in clusters:
            for k in self.contract_keys:
                for item in cluster.get(k, []):
                    qty = self._safe_float(item.qty)
                    ep = self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0))
                    contractor_totals[k] += qty * ep

        # Sum up prices from the parking lot
        for item in unmatched:
            if item.doc_key in contractor_totals:
                qty = self._safe_float(item.qty)
                ep = self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0))
                contractor_totals[item.doc_key] += qty * ep

        # Sort the internal keys list based on the calculated totals!
        self.contract_keys.sort(key=lambda k: contractor_totals[k])

        # --- Proceed with normal generation (Pandas will respect the sorted order) ---
        multi_cols = pd.MultiIndex.from_product(
            [self.metrics, [self.contract_names[k] for k in self.contract_keys]],
            names=['Metric', 'Contractor']
        )

        data_rows = []
        color_rows = []
        spans = []

        current_row = 0

        # Process Clusters
        for cluster in clusters:
            rows, colors, cluster_spans = self._process_cluster(cluster, current_row)
            data_rows.extend(rows)
            color_rows.extend(colors)
            spans.extend(cluster_spans)

            data_rows.append({c: "" for c in multi_cols})
            color_rows.append({c: False for c in multi_cols})
            current_row += len(rows) + 1

        # Process Parking Lot
        if unmatched:
            title_row = {c: "" for c in multi_cols}
            title_row[(self.metrics[0], self.contract_names[self.contract_keys[0]])] = "⚠️ ONGEKOPPELDE ITEMS"
            data_rows.append(title_row)
            color_rows.append({c: False for c in multi_cols})
            current_row += 1

            for item in unmatched:
                row, color = self._process_single_item(item)
                data_rows.append(row)
                color_rows.append(color)

        df_data = pd.DataFrame(data_rows, columns=multi_cols)
        df_colors = pd.DataFrame(color_rows, columns=multi_cols)

        return df_data, df_colors, spans

    def _process_cluster(self, cluster: dict, start_row: int) -> tuple[list[dict], list[dict], list[tuple]]:
        data_rows = []
        color_rows = []
        cluster_spans = []

        lists = {k: cluster.get(k, []) for k in self.contract_keys}
        max_len = max([len(lst) for lst in lists.values()] + [0])

        if max_len == 0:
            return [], [], []

        # Identify 1-to-N matches and register them for spanning
        if max_len > 1:
            for k in self.contract_keys:
                if len(lists[k]) == 1:
                    cluster_spans.append((start_row, max_len, self.contract_names[k]))

        # Track the totals for the entire cluster block across all N documents
        cluster_sums = {k: {'Aantal': 0.0, 'Eenheidsprijs': 0.0, 'Totaalprijs': 0.0} for k in self.contract_keys}

        for i in range(max_len):
            row_data = {}
            row_color = {c: False for c in pd.MultiIndex.from_product(
                [self.metrics, [self.contract_names[k] for k in self.contract_keys]])}
            row_items = {k: lists[k][i] if i < len(lists[k]) else None for k in self.contract_keys}

            for k, item in row_items.items():
                c_name = self.contract_names[k]
                if item:
                    qty = self._safe_float(item.qty)
                    ep = self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0))
                    tp = qty * ep

                    row_data[('Naam', c_name)] = str(item.name).strip()
                    row_data[('Aantal', c_name)] = qty
                    row_data[('Eenheid', c_name)] = str(item.unit).strip()
                    row_data[('Eenheidsprijs', c_name)] = ep
                    row_data[('Totaalprijs', c_name)] = tp

                    cluster_sums[k]['Aantal'] += qty
                    cluster_sums[k]['Eenheidsprijs'] += ep
                    cluster_sums[k]['Totaalprijs'] += tp
                else:
                    row_data[('Naam', c_name)] = ""
                    row_data[('Aantal', c_name)] = ""
                    row_data[('Eenheid', c_name)] = ""
                    row_data[('Eenheidsprijs', c_name)] = ""
                    row_data[('Totaalprijs', c_name)] = ""

            data_rows.append(row_data)
            color_rows.append(row_color)

        # --- REWRITTEN: N-DOCUMENT MIN/MAX HIGHLIGHTING ---
        # Find which documents actually have items in this cluster
        active_keys = [k for k in self.contract_keys if len(lists[k]) > 0]

        if len(active_keys) > 1:
            for metric in ['Aantal', 'Eenheidsprijs', 'Totaalprijs']:

                # Get sums for all active contractors
                sums_for_metric = {k: cluster_sums[k][metric] for k in active_keys}

                # Find the absolute min and max contractors dynamically
                min_k = min(sums_for_metric, key=sums_for_metric.get)
                max_k = max(sums_for_metric, key=sums_for_metric.get)

                diff = sums_for_metric[max_k] - sums_for_metric[min_k]

                if diff > 0.001:
                    # 1. Tuple Placement (Only apply difference tuples if exactly 2 are being compared)
                    if len(active_keys) == 2:
                        k1, k2 = active_keys[0], active_keys[1]
                        c1, c2 = self.contract_names[k1], self.contract_names[k2]
                        len_1, len_2 = len(lists[k1]), len(lists[k2])

                        target_c = self.contract_names[max_k]
                        target_diff = diff

                        # Flip the perspective if the min side is the 1-item parent
                        if len_1 == 1 and len_2 > 1 and max_k == k2:
                            target_c = c1
                            target_diff = -diff
                        elif len_2 == 1 and len_1 > 1 and max_k == k1:
                            target_c = c2
                            target_diff = -diff

                        if data_rows[0][(metric, target_c)] != "":
                            val = data_rows[0][(metric, target_c)]
                            data_rows[0][(metric, target_c)] = (val, target_diff)

                    # 2. Universal Min/Max Highlighting (Works for N documents!)
                    c_min = self.contract_names[min_k]
                    c_max = self.contract_names[max_k]

                    # Highlight the absolute cheapest Green, and absolute most expensive Red
                    for i in range(len(lists[min_k])): color_rows[i][(metric, c_min)] = '#d4edda'  # Green
                    for i in range(len(lists[max_k])): color_rows[i][(metric, c_max)] = '#f8d7da'  # Red

        return data_rows, color_rows, cluster_spans

    def _process_single_item(self, item) -> tuple[dict, dict]:
        # FIXED: Replaced item.side with item.doc_key!
        c_name = self.contract_names[item.doc_key]

        row_data = {c: "" for c in
                    pd.MultiIndex.from_product([self.metrics, [self.contract_names[k] for k in self.contract_keys]])}
        row_color = {c: False for c in row_data.keys()}

        qty = self._safe_float(item.qty)
        ep = self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0))
        tp = qty * ep

        row_data[('Naam', c_name)] = str(item.name).strip()
        row_data[('Aantal', c_name)] = qty
        row_data[('Eenheid', c_name)] = str(item.unit).strip()
        row_data[('Eenheidsprijs', c_name)] = ep
        row_data[('Totaalprijs', c_name)] = tp

        return row_data, row_color