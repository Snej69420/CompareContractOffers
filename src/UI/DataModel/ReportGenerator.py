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

    def generate(self, clusters: list[dict], unmatched: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame, list[tuple]]:
        multi_cols = pd.MultiIndex.from_product(
            [self.metrics, [self.contract_names[k] for k in self.contract_keys]],
            names=['Metric', 'Contractor']
        )

        data_rows = []
        color_rows = []
        spans = []  # --- NEW: Tracks (start_row, row_span, contractor_name) ---

        current_row = 0

        # Process Clusters
        for cluster in clusters:
            rows, colors, cluster_spans = self._process_cluster(cluster, current_row)
            data_rows.extend(rows)
            color_rows.extend(colors)
            spans.extend(cluster_spans)

            # Add an empty divider row after each cluster
            data_rows.append({c: "" for c in multi_cols})
            color_rows.append({c: False for c in multi_cols})

            # Update our global row tracker (+1 for the divider)
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

        # --- NEW: Track the totals for the entire cluster block ---
        cluster_sums = {k: {'Aantal': 0.0, 'Eenheidsprijs': 0.0, 'Totaalprijs': 0.0} for k in self.contract_keys}

        for i in range(max_len):
            row_data = {}
            row_color = {c: False for c in pd.MultiIndex.from_product(
                [self.metrics, [self.contract_names[k] for k in self.contract_keys]])}
            row_items = {k: lists[k][i] if i < len(lists[k]) else None for k in self.contract_keys}

            # Populate Data
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

                    # Add to cluster totals
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

        # --- REWRITTEN: Cluster-Level Highlight & Magnitude Logic ---
        if len(self.contract_keys) > 1:
            k1, k2 = self.contract_keys[0], self.contract_keys[1]
            c1, c2 = self.contract_names[k1], self.contract_names[k2]

            len_1 = len(lists[k1])
            len_2 = len(lists[k2])

            # Only perform math if both sides actually have items
            if len_1 > 0 and len_2 > 0:
                for metric in ['Aantal', 'Eenheidsprijs', 'Totaalprijs']:
                    sum1 = cluster_sums[k1][metric]
                    sum2 = cluster_sums[k2][metric]
                    diff = sum2 - sum1

                    if abs(diff) > 0.001:
                        # 1. Smart Tuple Placement
                        target_c = c2
                        target_diff = diff

                        # If C1 is the ONE side, put the tuple on C1 and flip the perspective!
                        if len_1 == 1 and len_2 > 1:
                            target_c = c1
                            target_diff = -diff  # "I am €X cheaper/more expensive than the sum of C2"

                        # Apply tuple to the first row of the chosen contractor
                        if data_rows[0][(metric, target_c)] != "":
                            val = data_rows[0][(metric, target_c)]
                            data_rows[0][(metric, target_c)] = (val, target_diff)

                        # 2. Color ALL rows inside the MANY side
                        if diff > 0:  # C2 is more expensive overall
                            for i in range(len_1): color_rows[i][(metric, c1)] = '#d4edda'  # Green
                            for i in range(len_2): color_rows[i][(metric, c2)] = '#f8d7da'  # Red
                        else:  # C2 is cheaper overall
                            for i in range(len_1): color_rows[i][(metric, c1)] = '#f8d7da'  # Red
                            for i in range(len_2): color_rows[i][(metric, c2)] = '#d4edda'  # Green

        return data_rows, color_rows, cluster_spans

    def _process_single_item(self, item) -> tuple[dict, dict]:
        # [Keep this exactly as you had it]
        c_name = self.contract_names[item.side]
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