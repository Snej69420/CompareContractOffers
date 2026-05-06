import pandas as pd


class ReportGenerator:
    def __init__(self, contract_names: dict[str, str]):
        self.contract_keys = list(contract_names.keys())
        self.contract_names = contract_names
        self.column_names = ['Naam', 'Hoev', 'EH', 'EP', 'Tot', '%']

    def _safe_float(self, val) -> float:
        try:
            if isinstance(val, str): val = val.replace(',', '.')
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def generate(self, norm_clusters: list[dict], norm_unmatched: list[dict]) -> tuple:
        contractor_totals = {k: 0.0 for k in self.contract_keys}

        # Calculate totals for overview (excluding "Buiten Scope" items)
        all_blocks = [c for c in norm_clusters if not c.get('is_excluded', False)] + norm_unmatched
        for block in all_blocks:
            lists = block.get('items', block)
            for k in self.contract_keys:
                items = lists.get(k, [])
                cost = sum(
                    self._safe_float(i.qty) * self._safe_float(i.raw_data.get('Eenheidsprijs', 0.0)) for i in items)
                contractor_totals[k] += cost

        # Sort contractors so cheapest is on the left
        self.contract_keys.sort(key=lambda k: contractor_totals[k])

        multi_cols = pd.MultiIndex.from_product(
            [[self.contract_names[k] for k in self.contract_keys], self.column_names],
            names=['Contractor', 'Metric']
        )

        data_rows, color_rows, v_spans, h_spans = [], [], [], []
        total_cols = len(self.contract_keys) * len(self.column_names)

        # Headers
        header_row = {c: "" for c in multi_cols}
        header_color = {c: '#d1d9e6' for c in multi_cols}
        for i, k in enumerate(self.contract_keys):
            c_name = self.contract_names[k]
            header_row[(c_name, self.column_names[0])] = c_name.upper()
            h_spans.append((0, i * len(self.column_names), 1, len(self.column_names)))

        data_rows.append(header_row)
        color_rows.append(header_color)
        current_row = 1

        def append_block(block, is_excluded=False):
            nonlocal current_row
            rows, colors, cluster_spans = self._process_cluster(block, current_row, multi_cols, is_excluded)
            if rows:
                data_rows.extend(rows)
                color_rows.extend(colors)
                v_spans.extend(cluster_spans)
                data_rows.append({c: "" for c in multi_cols})
                color_rows.append({c: False for c in multi_cols})
                current_row += len(rows) + 1

        # Included Clusters
        for cluster in [c for c in norm_clusters if not c.get('is_excluded', False)]:
            append_block(cluster)

        # Unmatched Items
        if norm_unmatched:
            title_row, c_row = {c: "" for c in multi_cols}, {c: '#e2e3e5' for c in multi_cols}
            title_row[(self.contract_names[self.contract_keys[0]], self.column_names[0])] = "ONGEKOPPELDE ITEMS"
            data_rows.append(title_row)
            color_rows.append(c_row)
            h_spans.append((current_row, 0, 1, total_cols))
            current_row += 1
            for pseudo_cluster in norm_unmatched: append_block(pseudo_cluster)

        # Excluded Clusters
        excluded_clusters = [c for c in norm_clusters if c.get('is_excluded', False)]
        if excluded_clusters:
            title_row, c_row = {c: "" for c in multi_cols}, {c: '#e2e3e5' for c in multi_cols}
            title_row[(self.contract_names[self.contract_keys[0]], self.column_names[0])] = "ONGEVRAAGDE / BUITEN SCOPE"
            data_rows.append(title_row)
            color_rows.append(c_row)
            h_spans.append((current_row, 0, 1, total_cols))
            current_row += 1
            for cluster in excluded_clusters: append_block(cluster, is_excluded=True)

        # --- PROJECT OVERVIEW (Bottom Block) ---
        min_tot = min(contractor_totals.values()) if contractor_totals else 0.0

        overview_title = {c: "" for c in multi_cols}
        overview_title[(self.contract_names[self.contract_keys[0]], self.column_names[0])] = "PROJECT OVERZICHT"
        data_rows.append(overview_title)
        color_rows.append({c: '#c3e6cb' for c in multi_cols})  # Gentle green background
        h_spans.append((current_row, 0, 1, total_cols))
        current_row += 1

        overview_data = {c: "" for c in multi_cols}
        overview_color = {c: False for c in multi_cols}

        for k in self.contract_keys:
            c_name = self.contract_names[k]
            total = contractor_totals[k]
            pct_diff = (total - min_tot) / min_tot if min_tot > 0 else 0.0

            overview_data[(c_name, 'Naam')] = "Totaal Project:"
            overview_data[(c_name, 'Tot')] = total

            overview_data[(c_name, '%')] = f"+{pct_diff * 100:.1f}%" if pct_diff > 0.001 else "0.0%"

        data_rows.append(overview_data)
        color_rows.append(overview_color)

        return pd.DataFrame(data_rows, columns=multi_cols), pd.DataFrame(color_rows,
                                                                         columns=multi_cols), v_spans, h_spans

    def _process_cluster(self, cluster: dict, start_row: int, multi_cols, is_excluded=False) -> tuple:
        data_rows, color_rows, cluster_spans = [], [], []
        lists = cluster.get('items', cluster)

        max_len = max(len(lists.get(k, [])) for k in self.contract_keys)

        # Calculate cluster logic for UI %
        contractor_costs = {}
        for k in self.contract_keys:
            items = lists.get(k, [])
            valid_items = [i for i in items if
                           not getattr(i, 'is_unmatched_blank', False) and not getattr(i, 'is_missing', False)]
            if valid_items:
                contractor_costs[k] = sum(
                    self._safe_float(i.qty) * self._safe_float(i.raw_data.get('Eenheidsprijs', 0.0)) for i in
                    valid_items)

        valid_costs = [c for c in contractor_costs.values() if c > 0]
        min_cost = min(valid_costs) if valid_costs and not is_excluded else None

        if max_len > 1:
            for k in self.contract_keys:
                if len(lists.get(k, [])) <= 1:
                    cluster_spans.append((start_row, max_len, self.contract_names[k]))

        for i in range(max_len):
            row_data = {c: "" for c in multi_cols}
            row_color = {c: False for c in multi_cols}
            for k in self.contract_keys:
                c_name = self.contract_names[k]
                items = lists.get(k, [])

                # Apply Percentage on the first row of the cluster for UI
                if i == 0 and min_cost and k in contractor_costs:
                    pct = (contractor_costs[k] - min_cost) / min_cost
                    if pct > 0.001:
                        row_data[(c_name, '%')] = f"+{pct * 100:.1f}%"
                    else:
                        row_data[(c_name, '%')] = "0.0%"

                if i < len(items):
                    item = items[i]
                    qty, ep = self._safe_float(item.qty), self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0))

                    if getattr(item, 'is_unmatched_blank', False):
                        for m in self.column_names: row_color[(c_name, m)] = '#fff3cd'
                    else:
                        row_data[(c_name, 'Naam')], row_data[(c_name, 'Hoev')] = item.name, qty
                        row_data[(c_name, 'EH')], row_data[(c_name, 'EP')] = item.unit, ep
                        row_data[(c_name, 'Tot')] = qty * ep
                        if getattr(item, 'is_missing', False):
                            for m in self.column_names: row_color[(c_name, m)] = '#fff3cd'

            data_rows.append(row_data)
            color_rows.append(row_color)

        return data_rows, color_rows, cluster_spans