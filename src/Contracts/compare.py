from src.Contracts.preprocessing import TextNormalizer
from src.Contracts.scoring import ScoringEngine


class ContractProcessor:
    def __init__(self):
        self.engine = ScoringEngine()
        self.norm = TextNormalizer()
        self.is_cancelled = False

        # --- CONFIGURATIE FLAGS ---
        self.ENABLE_UNIT_PENALTY = False  # Zet op True om hard te straffen voor verschillende eenheden (m2 vs lm)
        self.ENABLE_VARIANCE_PENALTY = False  # Zet op True om "parasiet" items uit een groep te filteren
        self.ENABLE_QUANTITY_BONUS = True  # Zet op True om +0.10 te geven als de hoeveelheden bijna exact matchen

    def process(self, master_df, target_df):
        self.is_cancelled = False
        master_cats = master_df['Categorie'].dropna().astype(str).unique().tolist()
        target_cats = target_df['Categorie'].dropna().astype(str).unique().tolist()

        category_results = {}
        for t_cat in target_cats:
            if self.is_cancelled:
                raise InterruptedError("Geannuleerd")

            t_clean = self.norm.clean_text(t_cat)
            cat_hits = self.engine.get_hybrid_score(t_clean, master_cats, top_k=3)

            scores_dict = {res['master_text']: res['cross_score'] for res in cat_hits}
            category_results[t_cat] = {
                'scores': scores_dict,
                'best_match': cat_hits[0]['master_text'] if cat_hits else None
            }

        item_mapping = {}
        lump_sum_units = ['ff', 'sog', 's.o.g.']

        # --- STAP 1: STANDAARD SCORING ---
        for t_cat in target_cats:
            if self.is_cancelled:
                raise InterruptedError("Geannuleerd")

            item_mapping[t_cat] = {}
            t_subset = target_df[target_df['Categorie'] == t_cat]

            for m_cat in master_cats:
                item_mapping[t_cat][m_cat] = {}
                m_subset = master_df[master_df['Categorie'] == m_cat]

                m_names = m_subset['Naam'].tolist()
                m_clean_list = [self.norm.clean_text(n) for n in m_names]

                for _, t_row in t_subset.iterrows():
                    t_name = str(t_row['Naam']).strip()
                    t_clean = self.norm.clean_text(t_name)
                    t_unit = self.norm.normalize_unit(t_row.get('Eenheid', ''))

                    try:
                        t_qty = float(t_row.get('Aantal', 0))
                    except:
                        t_qty = 0.0

                    k = min(len(m_clean_list), 10)
                    ai_hits = self.engine.get_hybrid_score(t_clean, m_clean_list, top_k=k)

                    best_m_name = None
                    best_total_score = -1
                    scores_breakdown = {}

                    for hit in ai_hits:
                        m_idx = hit['master_index']
                        m_row = m_subset.iloc[m_idx]
                        m_name = m_row['Naam']
                        m_unit = self.norm.normalize_unit(m_row.get('Eenheid', ''))

                        try:
                            m_qty = float(m_row.get('Aantal', 0))
                        except:
                            m_qty = 0.0

                        base_score = hit['cross_score']
                        unit_penalty = 0.0
                        qty_bonus = 0.0

                        is_lump_sum = (t_unit in lump_sum_units) or (m_unit in lump_sum_units)

                        # Optionele Unit Penalty
                        if self.ENABLE_UNIT_PENALTY and not is_lump_sum:
                            if t_unit and m_unit and t_unit != m_unit:
                                unit_penalty = -0.40

                        # Optionele Quantity Bonus
                        if self.ENABLE_QUANTITY_BONUS and not is_lump_sum:
                            if m_qty > 0 and t_qty > 0:
                                margin = abs(m_qty - t_qty) / max(m_qty, t_qty)
                                if margin <= 0.05:
                                    qty_bonus = 0.10

                        total = max(0.0, min(round(base_score + unit_penalty + qty_bonus, 3), 1.0))

                        scores_breakdown[m_name] = {
                            'total': total,
                            'text': round(base_score, 3),
                            'unit': unit_penalty,
                            'qty': qty_bonus,
                            'variance': 0.0
                        }

                        if total > best_total_score:
                            best_total_score = total
                            best_m_name = m_name

                    item_mapping[t_cat][m_cat][t_name] = {
                        'scores': scores_breakdown,
                        'best_match': best_m_name
                    }

        # --- STAP 2: OPTIONELE GROEPS VARIANTIE PENALTY ---
        if self.ENABLE_VARIANCE_PENALTY:
            master_max_scores = {}
            for t_cat, m_cats in item_mapping.items():
                for m_cat, t_items in m_cats.items():
                    for t_name, match_data in t_items.items():
                        for m_name, scores in match_data['scores'].items():
                            if m_name not in master_max_scores or scores['total'] > master_max_scores[m_name]:
                                master_max_scores[m_name] = scores['total']

            VARIANCE_LIMIT = 0.25
            for t_cat, m_cats in item_mapping.items():
                for m_cat, t_items in m_cats.items():
                    for t_name, match_data in t_items.items():
                        best_m_name = None
                        best_total_score = -1

                        for m_name, scores in match_data['scores'].items():
                            alpha_score = master_max_scores.get(m_name, 0)
                            current_total = scores['total']

                            if (alpha_score - current_total) > VARIANCE_LIMIT:
                                penalty = -0.40
                                scores['variance'] = penalty
                                scores['total'] = max(0.0, current_total + penalty)

                            if scores['total'] > best_total_score:
                                best_total_score = scores['total']
                                best_m_name = m_name

                        match_data['best_match'] = best_m_name

        return {
            'categories': category_results,
            'items': item_mapping
        }