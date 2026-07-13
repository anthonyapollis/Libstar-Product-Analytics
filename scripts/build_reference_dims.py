"""Build Libstar reference dimension CSVs from the seed model.

These dims are the single source of truth used by the data generator, the
Synapse views, the Qlik load script, the ebook and the Excel report, so that
every deliverable reports the same numbers.

Source: Libstar public 'Our business' / 'Operations' pages (captured 2026-07-06).
"""

import os

import pandas as pd

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "reference")

PRODUCT_GROUPS = [
    ("perishable-products", "Perishable products", 1),
    ("ambient-products", "Ambient products", 2),
]

# category_id, group_id, name
CATEGORIES = [
    ("dairy", "perishable-products", "Dairy"),
    ("convenience-meals", "perishable-products", "Convenience Meals"),
    ("value-added-meats", "perishable-products", "Value-added Meats"),
    ("baby", "perishable-products", "Baby"),
    ("fresh-mushrooms", "perishable-products", "Fresh Mushrooms"),
    ("dry-condiments", "ambient-products", "Dry condiments"),
    ("wet-condiments", "ambient-products", "Wet condiments"),
    ("meal-ingredients", "ambient-products", "Meal ingredients"),
    ("baking", "ambient-products", "Baking"),
    ("snacking", "ambient-products", "Snacking"),
    ("spreads", "ambient-products", "Spreads"),
    ("beverages", "ambient-products", "Beverages"),
]

BRAND_SOLUTIONS = [
    ("libstar-brands", "Libstar Brands"),
    ("principal-brands", "Principal Brands"),
    ("private-label-dealer-own", "Private label and dealer-own brands"),
]

# brand, solution_id, [category_ids]
BRANDS = [
    ("Lancewood", "libstar-brands", ["dairy"]),
    ("Denny Mushrooms", "libstar-brands", ["fresh-mushrooms"]),
    ("Millennium Foods", "libstar-brands", ["convenience-meals"]),
    ("Finlar Fine Foods", "libstar-brands", ["value-added-meats", "convenience-meals"]),
    ("Umatie", "libstar-brands", ["baby"]),
    ("Rialto", "libstar-brands", ["meal-ingredients", "beverages"]),
    ("Cape Herb & Spice", "libstar-brands", ["dry-condiments"]),
    ("Khoisan Gourmet", "libstar-brands", ["dry-condiments", "beverages"]),
    ("Cape Foods", "libstar-brands", ["dry-condiments", "meal-ingredients"]),
    ("Montagu Foods", "libstar-brands", ["snacking", "meal-ingredients"]),
    ("Cecil Vinegar", "libstar-brands", ["wet-condiments"]),
    ("Dickon Hall Foods", "libstar-brands", ["wet-condiments", "spreads"]),
    ("Cape Coastal Honey", "libstar-brands", ["spreads"]),
    ("Goldcrest", "libstar-brands", ["spreads", "meal-ingredients"]),
    ("Chamonix", "libstar-brands", ["beverages", "baking"]),
    ("Amaro Foods", "libstar-brands", ["baking"]),
    ("Cani", "libstar-brands", ["baking"]),
    ("Ambassador Foods", "libstar-brands", ["snacking"]),
    ("Bonne Maman", "principal-brands", ["spreads"]),
    ("Kikkoman", "principal-brands", ["wet-condiments"]),
    ("Tabasco", "principal-brands", ["wet-condiments"]),
    ("Maille", "principal-brands", ["wet-condiments"]),
    ("Retailer Brands", "private-label-dealer-own",
     [c[0] for c in CATEGORIES]),
]

SALES_CHANNELS = [
    ("retail-wholesale", "Retail and wholesale", 0.62),
    ("food-service", "Food service", 0.18),
    ("industrial-contract-manufacturing", "Industrial and contract manufacturing", 0.12),
    ("export", "Export", 0.08),
]

# province, has_libstar_operations (per business_unit_region seed), weight for
# sales distribution (rough population/economy proxy)
PROVINCES = [
    ("Western Cape", True, 0.22),
    ("Gauteng", True, 0.30),
    ("KwaZulu-Natal", True, 0.17),
    ("Eastern Cape", True, 0.09),
    ("Mpumalanga", True, 0.06),
    ("Limpopo", False, 0.05),
    ("North West", False, 0.04),
    ("Free State", False, 0.04),
    ("Northern Cape", False, 0.03),
]


def main() -> None:
    os.makedirs(OUT, exist_ok=True)

    pd.DataFrame(PRODUCT_GROUPS, columns=["group_id", "product_group", "display_order"]) \
        .to_csv(os.path.join(OUT, "dim_product_group.csv"), index=False)

    pd.DataFrame(CATEGORIES, columns=["category_id", "group_id", "category"]) \
        .to_csv(os.path.join(OUT, "dim_category.csv"), index=False)

    pd.DataFrame(BRAND_SOLUTIONS, columns=["solution_id", "brand_solution"]) \
        .to_csv(os.path.join(OUT, "dim_brand_solution.csv"), index=False)

    rows = []
    for brand, sol, cats in BRANDS:
        for c in cats:
            rows.append((brand, sol, c))
    pd.DataFrame(rows, columns=["brand", "solution_id", "category_id"]) \
        .to_csv(os.path.join(OUT, "dim_brand_category.csv"), index=False)

    pd.DataFrame(SALES_CHANNELS, columns=["channel_id", "sales_channel", "sales_weight"]) \
        .to_csv(os.path.join(OUT, "dim_sales_channel.csv"), index=False)

    pd.DataFrame(PROVINCES, columns=["province", "has_libstar_operations", "sales_weight"]) \
        .to_csv(os.path.join(OUT, "dim_province.csv"), index=False)

    print("reference dims written to", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
