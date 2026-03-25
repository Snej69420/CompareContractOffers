from Matcher import ContractMatcher
import pandas as pd


def print_results(model_name, results):
    print(f"\n{'=' * 50}")
    print(f"MODEL: {model_name}")
    print(f"{'=' * 50}")

    print("\n--- CATEGORY MATCHES ---")
    for target_cat, match_info in results['categories'].items():
        matched_to = match_info['match'] if match_info['match'] else "NO MATCH (None)"
        print(f"[{target_cat}] mapped to -> [{matched_to}] (Score: {match_info['score']})")

    print("\n--- ITEM MATCHES ---")
    for target_cat, items in results['items'].items():
        print(f"Under Category: {target_cat}")
        for target_item, match_info in items.items():
            matched_to = match_info['match'] if match_info['match'] else "NO MATCH (None)"
            print(f"  - [{target_item}] mapped to -> [{matched_to}] (Score: {match_info['score']})")
    print("\n")


# 1. Setup Dummy Data
df_master = pd.DataFrame({
    'Categorie': ['Grondwerken', 'Grondwerken', 'Sanitair', 'Elektriciteit'],
    'Naam': ['Graven fundering', 'Afvoer aarde', 'Installatie toilet', 'Trekken kabels']
})

# Target contract has only 2 items across 2 categories
df_target = pd.DataFrame({
    'Categorie': ['Graafwerken', 'Loodgieterij'],
    'Naam': ['Uitgraven sleuven', 'Plaatsen wc']
})

# 2. Define the models we want to test
model_1 = 'paraphrase-multilingual-MiniLM-L12-v2'
model_2 = 'paraphrase-multilingual-mpnet-base-v2'
model_3 = 'distiluse-base-multilingual-cased-v2'
model_4 = 'NetherlandsForensicInstitute/robbert-2022-dutch-sentence-transformers'
model_5 = 'clips/e5-base-trm-nl'

# 3. Run and Compare
print("Loading models... (this might take a few seconds if downloading for the first time)")

matcher_1 = ContractMatcher(model_name=model_1)
results_1 = matcher_1.match_contracts(df_master, df_target, category_threshold=0.65, item_threshold=0.50)

matcher_2 = ContractMatcher(model_name=model_2)
results_2 = matcher_2.match_contracts(df_master, df_target, category_threshold=0.65, item_threshold=0.50)

matcher_3 = ContractMatcher(model_name=model_3)
results_3 = matcher_3.match_contracts(df_master, df_target, category_threshold=0.65, item_threshold=0.50)

matcher_4 = ContractMatcher(model_name=model_4)
results_4 = matcher_4.match_contracts(df_master, df_target, category_threshold=0.65, item_threshold=0.50)

matcher_5 = ContractMatcher(model_name=model_5)
results_5 = matcher_5.match_contracts(df_master, df_target, category_threshold=0.65, item_threshold=0.50)

# 4. Print the comparison
print_results(model_1, results_1)
print_results(model_2, results_2)
print_results(model_3, results_3)
print_results(model_4, results_4)
print_results(model_5, results_5)