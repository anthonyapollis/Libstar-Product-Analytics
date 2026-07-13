"""Generate a deliberately dirty Libstar-themed product catalog (v2).

Produces N_ROWS product records across gzipped CSV chunks in data/raw/.
Brands, categories, brand solutions, sales channels and provinces come from
data/reference/dim_*.csv (built by build_reference_dims.py) so the whole
pipeline (ADF -> Synapse -> Qlik / ebook / Excel) reconciles to one model.

Injected mess for Azure Data Factory to clean:

- duplicate product_ids (exact dupes appended per chunk)
- prices in mixed formats: "1234.56", "R 1,234.56", "ZAR1234", negatives, "N/A", blanks
- category names with casing/typo variants AND legacy business-unit names
  ("Groceries", "Baking and baking aids", "Snacks and confectionery",
  "Perishables") that must be resolved via brand lookup
- brand names with casing/whitespace/'and'-vs-'&' variants, plus NULL/unknown
- dates in ISO / dd/MM/yyyy / MM-dd-yyyy formats, some invalid or blank
- weights randomly recorded in grams instead of kilograms, some negative
- stock quantities occasionally spelled out as words or negative
- is_active as Y/N/1/0/TRUE/false/yes/no/Active
- provinces with casing variants and abbreviations (WC, GP, KZN)
- sales channels with casing variants and blanks
- ratings outside the 0-5 range

Seeded for reproducibility.
"""

import gzip
import io
import os

import numpy as np
import pandas as pd

N_ROWS = 5_000_000
CHUNK = 500_000
SEED = 42
BASE = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR = os.path.join(BASE, "data", "raw")
REF_DIR = os.path.join(BASE, "data", "reference")

LEGACY_CATEGORIES = [
    "Groceries", "Baking and baking aids", "Snacks and confectionery",
    "Perishables", "Household and personal care",
]

NAME_NOUNS = {
    "Dairy": ["Cheddar Block", "Gouda Wedge", "Cream Cheese Tub", "Plain Yoghurt",
              "Double Cream Yoghurt", "Mozzarella", "Feta Rounds", "Cottage Cheese"],
    "Convenience Meals": ["Lasagne Ready Meal", "Butter Chicken Meal", "Cottage Pie",
                          "Mac & Cheese Meal", "Veg Curry Meal", "Bobotie Ready Meal"],
    "Value-added Meats": ["Crumbed Chicken Schnitzel", "Beef Burger Patties",
                          "Chicken Nuggets", "Cordon Bleu", "Peri-Peri Chicken Strips"],
    "Baby": ["Organic Baby Puree", "Baby Cereal", "Toddler Snack Puffs", "Fruit Pouch"],
    "Fresh Mushrooms": ["White Button Mushrooms", "Portabellini Punnet",
                        "Brown Mushrooms", "Exotic Mushroom Mix"],
    "Dry condiments": ["Atlantic Sea Salt Grinder", "Peri-Peri Rub", "BBQ Spice Blend",
                       "Masala Blend", "Lemon & Herb Seasoning"],
    "Wet condiments": ["Soy Sauce", "Dijon Mustard", "Pepper Sauce", "White Wine Vinegar",
                       "Balsamic Reduction", "Mayonnaise", "Sweet Chilli Sauce"],
    "Meal ingredients": ["Risotto Rice", "Couscous", "Tomato Paste", "Coconut Milk",
                         "Olive Oil Blend", "Pasta Shells"],
    "Baking": ["Croissants", "Ciabatta Rolls", "Muffin Mix", "Artisan Sourdough", "Wraps"],
    "Snacking": ["Dried Mango Strips", "Trail Mix", "Salted Almonds", "Fruit Bars",
                 "Biltong Snack Pack"],
    "Spreads": ["Strawberry Preserve", "Fynbos Honey", "Apricot Jam", "Chocolate Spread",
                "Orange Marmalade"],
    "Beverages": ["Rooibos Tea", "Hot Chocolate", "Instant Cappuccino", "Green Tea",
                  "Iced Tea Concentrate"],
}

SIZES = ["125g", "250g", "400g", "500g", "750g", "1kg", "2kg", "250ml", "500ml", "750ml", "1L"]
ADJ = ["Premium", "Classic", "Organic", "Traditional", "Everyday", "Select", "Gourmet", "Family Pack"]

# category base prices (ZAR) and brand-solution multipliers give price real
# structure so the ML pricing model has signal to recover
CAT_BASE_PRICE = {
    "Dairy": 55.0, "Convenience Meals": 72.0, "Value-added Meats": 95.0,
    "Baby": 48.0, "Fresh Mushrooms": 36.0, "Dry condiments": 62.0,
    "Wet condiments": 52.0, "Meal ingredients": 66.0, "Baking": 42.0,
    "Snacking": 56.0, "Spreads": 74.0, "Beverages": 86.0,
}
SOLUTION_PRICE_MULT = {
    "libstar-brands": 1.0, "principal-brands": 1.35, "private-label-dealer-own": 0.8,
}

WORD_NUMBERS = ["twelve", "five", "twenty", "none", "out of stock"]
ACTIVE_VALUES = ["Y", "N", "1", "0", "TRUE", "false", "yes", "no", "Active", ""]

PROVINCE_ABBR = {
    "Western Cape": "WC", "Gauteng": "GP", "KwaZulu-Natal": "KZN",
    "Eastern Cape": "EC", "Mpumalanga": "MP", "Limpopo": "LP",
    "North West": "NW", "Free State": "FS", "Northern Cape": "NC",
}


def dirty_string(rng, s: str) -> str:
    r = rng.random()
    if r < 0.3:
        return s.upper()
    if r < 0.55:
        return s.lower()
    if r < 0.75:
        return f" {s} "
    if r < 0.9 and "&" in s:
        return s.replace("&", "and")
    return s + "  "


def load_refs():
    cats = pd.read_csv(os.path.join(REF_DIR, "dim_category.csv"))
    bc = pd.read_csv(os.path.join(REF_DIR, "dim_brand_category.csv"))
    ch = pd.read_csv(os.path.join(REF_DIR, "dim_sales_channel.csv"))
    prov = pd.read_csv(os.path.join(REF_DIR, "dim_province.csv"))
    bc = bc.merge(cats, on="category_id")
    # weight brand-category pairs so private label doesn't dominate
    w = bc["solution_id"].map({
        "libstar-brands": 3.0, "principal-brands": 2.0, "private-label-dealer-own": 0.8,
    }).to_numpy()
    return bc, w / w.sum(), ch, prov


def make_chunk(rng, start_id, n, bc, bc_w, ch, prov):
    pair_idx = rng.choice(len(bc), n, p=bc_w)
    brands = bc["brand"].to_numpy()[pair_idx]
    cats = bc["category"].to_numpy()[pair_idx]

    # brand column: ~12% dirty variant, ~3% junk
    brand_col = brands.astype(object).copy()
    br = rng.random(n)
    dirty_b = br < 0.12
    brand_col[dirty_b] = [dirty_string(rng, b) for b in brands[dirty_b]]
    junk_b = (br >= 0.12) & (br < 0.15)
    brand_col[junk_b] = rng.choice(["NULL", "unknown", ""], int(junk_b.sum()))

    # category column: ~12% casing/typo variant, ~6% legacy business-unit name
    cat_col = cats.astype(object).copy()
    cr = rng.random(n)
    dirty_c = cr < 0.12
    cat_col[dirty_c] = [dirty_string(rng, c) for c in cats[dirty_c]]
    legacy_c = (cr >= 0.12) & (cr < 0.18)
    cat_col[legacy_c] = rng.choice(LEGACY_CATEGORIES, int(legacy_c.sum()))

    names = np.array([
        f"{rng.choice(ADJ)} {rng.choice(NAME_NOUNS[c])} {rng.choice(SIZES)}"
        for c in cats
    ], dtype=object)
    dirty_name = rng.random(n) < 0.08
    names[dirty_name] = [
        (s.upper() if rng.random() < 0.5 else s.lower()).replace(" ", "  ", 1)
        for s in names[dirty_name]
    ]

    weight = np.round(rng.gamma(1.5, 0.5, n) + 0.05, 3)

    cat_base = np.array([CAT_BASE_PRICE[c] for c in cats])
    sol_mult = np.array([SOLUTION_PRICE_MULT[s] for s in bc["solution_id"].to_numpy()[pair_idx]])
    base_price = np.round(
        np.maximum(cat_base * sol_mult * (weight / 0.5) ** 0.35
                   * rng.lognormal(0.0, 0.22, n), 8.99), 2)
    price_col = base_price.astype(object)
    r = rng.random(n)
    fmt_r = r < 0.12
    fmt_zar = (r >= 0.12) & (r < 0.18)
    fmt_neg = (r >= 0.18) & (r < 0.20)
    fmt_na = (r >= 0.20) & (r < 0.23)
    price_col[fmt_r] = [f"R {p:,.2f}" for p in base_price[fmt_r]]
    price_col[fmt_zar] = [f"ZAR{p:.2f}" for p in base_price[fmt_zar]]
    price_col[fmt_neg] = np.round(-base_price[fmt_neg], 2)
    price_col[fmt_na] = rng.choice(["N/A", "", "NULL"], int(fmt_na.sum()))

    cost = np.round(base_price * rng.uniform(0.5, 0.8, n), 2)

    weight_col = weight.astype(object)
    w = rng.random(n)
    weight_col[w < 0.07] = np.round(weight[w < 0.07] * 1000, 0)
    weight_col[(w >= 0.07) & (w < 0.09)] = -weight[(w >= 0.07) & (w < 0.09)]
    weight_col[(w >= 0.09) & (w < 0.12)] = ""

    stock = rng.integers(0, 500, n).astype(object)
    s = rng.random(n)
    stock[s < 0.03] = rng.choice(WORD_NUMBERS, int((s < 0.03).sum()))
    neg_s = (s >= 0.03) & (s < 0.05)
    stock[neg_s] = -rng.integers(1, 50, int(neg_s.sum()))

    # price-elastic volumes: cheaper products move more units
    units = np.round(rng.gamma(2.0, 2200.0, n) * (60.0 / base_price) ** 0.5, 0).astype(object)
    u = rng.random(n)
    units[u < 0.02] = rng.choice(WORD_NUMBERS, int((u < 0.02).sum()))
    units[(u >= 0.02) & (u < 0.03)] = ""

    days = rng.integers(0, 2000, n)
    base = pd.Timestamp("2021-01-01") + pd.to_timedelta(days, unit="D")
    date_col = np.empty(n, dtype=object)
    d = rng.random(n)
    iso = d < 0.6
    dmy = (d >= 0.6) & (d < 0.8)
    mdy = (d >= 0.8) & (d < 0.93)
    bad = (d >= 0.93) & (d < 0.96)
    date_col[iso] = base[iso].strftime("%Y-%m-%d")
    date_col[dmy] = base[dmy].strftime("%d/%m/%Y")
    date_col[mdy] = base[mdy].strftime("%m-%d-%Y")
    date_col[bad] = rng.choice(["2023/13/45", "31-02-2022", "not_a_date", "0000-00-00"], int(bad.sum()))
    date_col[d >= 0.96] = ""

    channels = rng.choice(ch["sales_channel"].to_numpy(), n, p=ch["sales_weight"].to_numpy())
    chan_col = channels.astype(object)
    cx = rng.random(n)
    dirty_ch = cx < 0.1
    chan_col[dirty_ch] = [dirty_string(rng, c) for c in channels[dirty_ch]]
    chan_col[(cx >= 0.1) & (cx < 0.12)] = ""

    pw = prov["sales_weight"].to_numpy()
    provinces = rng.choice(prov["province"].to_numpy(), n, p=pw / pw.sum())
    prov_col = provinces.astype(object)
    px = rng.random(n)
    abbr_p = px < 0.08
    prov_col[abbr_p] = [PROVINCE_ABBR[p] for p in provinces[abbr_p]]
    dirty_p = (px >= 0.08) & (px < 0.16)
    prov_col[dirty_p] = [dirty_string(rng, p) for p in provinces[dirty_p]]
    prov_col[(px >= 0.16) & (px < 0.18)] = ""

    rating = np.round(rng.uniform(1.0, 5.0, n), 1).astype(object)
    rt = rng.random(n)
    rating[rt < 0.02] = rng.choice([99, -1, 10.5], int((rt < 0.02).sum()))
    rating[(rt >= 0.02) & (rt < 0.05)] = ""

    df = pd.DataFrame({
        "product_id": [f"LIB-{i:08d}" for i in range(start_id, start_id + n)],
        "sku": [f"SKU{rng.integers(10**8, 10**9)}" if rng.random() > 0.02 else "" for _ in range(n)],
        "product_name": names,
        "category": cat_col,
        "brand": brand_col,
        "sales_channel": chan_col,
        "province": prov_col,
        "price_zar": price_col,
        "cost_zar": cost,
        "weight_kg": weight_col,
        "stock_qty": stock,
        "units_sold_12m": units,
        "date_added": date_col,
        "is_active": rng.choice(ACTIVE_VALUES, n),
        "rating": rating,
    })

    dup_idx = rng.choice(n, int(n * 0.02), replace=False)
    df = pd.concat([df, df.iloc[dup_idx]], ignore_index=True)
    return df.sample(frac=1.0, random_state=int(rng.integers(0, 2**31))).reset_index(drop=True)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    bc, bc_w, ch, prov = load_refs()
    rng = np.random.default_rng(SEED)
    n_chunks = N_ROWS // CHUNK
    total = 0
    for c in range(n_chunks):
        df = make_chunk(rng, c * CHUNK, CHUNK, bc, bc_w, ch, prov)
        path = os.path.join(OUT_DIR, f"products_part_{c:02d}.csv.gz")
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        with gzip.open(path, "wb", compresslevel=6) as f:
            f.write(buf.getvalue())
        total += len(df)
        print(f"chunk {c + 1}/{n_chunks} written: {path} ({len(df):,} rows)", flush=True)
    print(f"DONE: {total:,} rows (target {N_ROWS:,} + ~2% duplicates)")


if __name__ == "__main__":
    main()
