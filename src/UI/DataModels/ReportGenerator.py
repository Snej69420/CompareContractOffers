import pandas as pd


class ReportGenerator:
    def __init__(self, contract_names: dict[str, str]):
        self.contract_keys = list(contract_names.keys())
        self.contract_names = contract_names
        self.metrics = ['Naam', 'Aantal', 'Eenheid', 'Eenheidsprijs', 'Totaal']

    def _safe_float(self, val) -> float:
        try:
            if isinstance(val, str): val = val.replace(',', '.')
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def generate(self, clusters: list[dict], unmatched: list) -> tuple[
        pd.DataFrame, pd.DataFrame, list[tuple], list[tuple]]:
        contractor_totals = {k: 0.0 for k in self.contract_keys}

        # --- 1. CALCULATE FAIR "APPLES-TO-APPLES" TOTALS ---
        included_clusters = [c for c in clusters if not c.get('is_excluded', False)]

        for cluster in included_clusters:
            lists = cluster.get('items', cluster)
            lists = {k: lists.get(k, []) for k in self.contract_keys}
            max_len = max([len(lst) for lst in lists.values()] + [0])

            # Calculate row by row
            for i in range(max_len):
                row_items = {k: lists[k][i] if i < len(lists[k]) else None for k in self.contract_keys}
                present_items = [item for item in row_items.values() if item is not None]
                if not present_items: continue

                # Get average unit price of contractors who INCLUDED the item
                avg_ep = sum(self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0)) for item in present_items) / len(
                    present_items)
                master_qty = self._safe_float(present_items[0].qty)

                for k, item in row_items.items():
                    if item:
                        qty = self._safe_float(item.qty)
                        ep = self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0))
                        contractor_totals[k] += qty * ep
                    else:
                        # Pad the missing contractor with the average cost
                        contractor_totals[k] += master_qty * avg_ep

        # Unmatched items are gaps for everyone else
        for item in unmatched:
            qty = self._safe_float(item.qty)
            ep = self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0))
            for k in self.contract_keys:
                contractor_totals[k] += qty * ep

        # Sort columns based on the FAIR total (cheapest to most expensive)
        self.contract_keys.sort(key=lambda k: contractor_totals[k])

        multi_cols = pd.MultiIndex.from_product(
            [[self.contract_names[k] for k in self.contract_keys], self.metrics],
            names=['Contractor', 'Metric']
        )

        data_rows, color_rows, v_spans, h_spans = [], [], [], []
        total_cols = len(self.contract_keys) * len(self.metrics)

        # --- 2. ROW 0: THE SPANNED CONTRACTOR HEADER ---
        header_row = {c: "" for c in multi_cols}
        header_color = {c: '#d1d9e6' for c in multi_cols}

        for i, k in enumerate(self.contract_keys):
            c_name = self.contract_names[k]
            header_row[(c_name, self.metrics[0])] = f"{c_name.upper()}"
            col_start = i * len(self.metrics)
            h_spans.append((0, col_start, 1, len(self.metrics)))

        data_rows.append(header_row)
        color_rows.append(header_color)
        current_row = 1

        # --- 3. PROCESS INCLUDED CLUSTERS ---
        for cluster in included_clusters:
            rows, colors, cluster_spans = self._process_cluster(cluster, current_row, multi_cols)
            if rows:
                data_rows.extend(rows)
                color_rows.extend(colors)
                v_spans.extend(cluster_spans)

                data_rows.append({c: "" for c in multi_cols})
                color_rows.append({c: False for c in multi_cols})
                current_row += len(rows) + 1

        # --- 4. EXCLUDED CLUSTERS (ONGEVRAAGDE ITEMS) ---
        excluded_clusters = [c for c in clusters if c.get('is_excluded', False)]
        if excluded_clusters:
            title_row = {c: "" for c in multi_cols}
            title_row[
                (self.contract_names[self.contract_keys[0]], self.metrics[0])] = "ONGEVRAAGDE / BUITEN SCOPE ITEMS"
            data_rows.append(title_row)

            title_color = {c: '#e2e3e5' for c in multi_cols}
            color_rows.append(title_color)
            h_spans.append((current_row, 0, 1, total_cols))
            current_row += 1

            for cluster in excluded_clusters:
                rows, colors, cluster_spans = self._process_cluster(cluster, current_row, multi_cols)
                if rows:
                    data_rows.extend(rows)
                    color_rows.extend(colors)
                    v_spans.extend(cluster_spans)

                    data_rows.append({c: "" for c in multi_cols})
                    color_rows.append({c: False for c in multi_cols})
                    current_row += len(rows) + 1

        # --- 5. PARKING LOT (UNMATCHED) ---
        if unmatched:
            title_row = {c: "" for c in multi_cols}
            title_row[(self.contract_names[self.contract_keys[0]], self.metrics[0])] = "ONGEKOPPELDE ITEMS"
            data_rows.append(title_row)

            title_color = {c: '#e2e3e5' for c in multi_cols}
            color_rows.append(title_color)
            h_spans.append((current_row, 0, 1, total_cols))
            current_row += 1

            for item in unmatched:
                row, color = self._process_single_item(item, multi_cols)
                data_rows.append(row)
                color_rows.append(color)

        df_data = pd.DataFrame(data_rows, columns=multi_cols)
        df_colors = pd.DataFrame(color_rows, columns=multi_cols)

        return df_data, df_colors, v_spans, h_spans

    def _process_cluster(self, cluster: dict, start_row: int, multi_cols) -> tuple[list[dict], list[dict], list[tuple]]:
        data_rows, color_rows, cluster_spans = [], [], []

        lists = cluster.get('items', cluster)
        lists = {k: lists.get(k, []) for k in self.contract_keys}

        max_len = max([len(lst) for lst in lists.values()] + [0])
        if max_len == 0: return [], [], []

        is_excluded = cluster.get('is_excluded', False)

        # Spanning for 1-to-N layout structure
        if max_len > 1:
            for k in self.contract_keys:
                if len(lists[k]) == 1:
                    cluster_spans.append((start_row, max_len, self.contract_names[k]))

        for i in range(max_len):
            row_data = {c: "" for c in multi_cols}
            row_color = {c: False for c in multi_cols}

            row_items = {k: lists[k][i] if i < len(lists[k]) else None for k in self.contract_keys}
            present_items = [item for item in row_items.values() if item is not None]
            if not present_items: continue

            avg_ep = sum(self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0)) for item in present_items) / len(
                present_items)
            master_item = present_items[0]
            master_qty = self._safe_float(master_item.qty)

            for k, item in row_items.items():
                c_name = self.contract_names[k]

                if item:
                    # 1. Standard Present Item
                    qty = self._safe_float(item.qty)
                    ep = self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0))
                    row_data[(c_name, 'Naam')] = str(item.name).strip()
                    row_data[(c_name, 'Aantal')] = qty
                    row_data[(c_name, 'Eenheid')] = str(item.unit).strip()
                    row_data[(c_name, 'Eenheidsprijs')] = ep
                    row_data[(c_name, 'Totaal')] = qty * ep

                elif not is_excluded:
                    # 2. APPLES TO APPLES: Artificial Padding (Uses calculated Average)
                    row_data[(c_name, 'Naam')] = str(master_item.name).strip()
                    row_data[(c_name, 'Aantal')] = master_qty
                    row_data[(c_name, 'Eenheid')] = str(master_item.unit).strip()
                    row_data[(c_name, 'Eenheidsprijs')] = avg_ep
                    row_data[(c_name, 'Totaal')] = master_qty * avg_ep

                    for m in self.metrics:
                        row_color[(c_name, m)] = '#fff3cd'

            data_rows.append(row_data)
            color_rows.append(row_color)

        return data_rows, color_rows, cluster_spans

    def _process_single_item(self, item, multi_cols) -> tuple[dict, dict]:
        """Unmatched items are artificially copied across all contractors."""
        row_data = {c: "" for c in multi_cols}
        row_color = {c: False for c in multi_cols}

        qty = self._safe_float(item.qty)
        ep = self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0))

        for k in self.contract_keys:
            c_name = self.contract_names[k]
            row_data[(c_name, 'Naam')] = str(item.name).strip()
            row_data[(c_name, 'Aantal')] = qty
            row_data[(c_name, 'Eenheid')] = str(item.unit).strip()
            row_data[(c_name, 'Eenheidsprijs')] = ep
            row_data[(c_name, 'Totaal')] = qty * ep

            # Highlight the artificial copies in yellow
            if k != item.doc_key:
                for m in self.metrics:
                    row_color[(c_name, m)] = '#fff3cd'

        return row_data, row_color