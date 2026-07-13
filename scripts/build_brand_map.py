"""Emit data/reference/brand_map.csv — the lookup ADF uses to resolve brands.

brand_key is lower-cased with ' and ' normalised to ' & ', matching the
normalisation the data flow applies to the dirty brand column.
primary_category resolves rows whose category is a legacy business-unit name.
"""

import os

import pandas as pd

REF = os.path.join(os.path.dirname(__file__), "..", "data", "reference")

bc = pd.read_csv(os.path.join(REF, "dim_brand_category.csv"))
cat = pd.read_csv(os.path.join(REF, "dim_category.csv"))
grp = pd.read_csv(os.path.join(REF, "dim_product_group.csv"))
sol = pd.read_csv(os.path.join(REF, "dim_brand_solution.csv"))

m = bc.merge(cat, on="category_id").merge(grp, on="group_id").merge(sol, on="solution_id")
first = m.drop_duplicates(subset=["brand"], keep="first")

out = pd.DataFrame({
    "bm_brand_key": first["brand"].str.lower().str.replace(" and ", " & ", regex=False),
    "bm_brand": first["brand"],
    "bm_brand_solution": first["brand_solution"],
    "bm_primary_category": first["category"],
    "bm_product_group": first["product_group"],
})
out.to_csv(os.path.join(REF, "brand_map.csv"), index=False)
print(f"brand_map.csv written ({len(out)} brands)")
