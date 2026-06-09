"""Generate a concise keyword-based MERCHANT_TO_CATEGORY_MAP.

Reads the existing merchant-to-category mapping, optional exact merchant
overrides, and the list of unique merchants, then distils a compact set of
keywords that reliably predict a merchant's category via substring matching.

Usage:
    pipenv run python scripts/generate_keyword_map.py
"""

import re
import csv
from math import ceil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UNIQUE_MERCHANTS_FILE = PROJECT_ROOT / "data" / "unique_merchants.csv"
EXACT_OVERRIDES_FILE = (
    PROJECT_ROOT / "data" / "merchant_category_overrides_2025_2026.yaml"
)
CONFIG_FILE = PROJECT_ROOT / "config.yaml"

# Minimum number of merchants a keyword must appear in to be eligible.
MIN_MERCHANT_FREQUENCY = 2

# A keyword must map to its dominant category at least this fraction of the
# time to be considered unambiguous (0.0-1.0).
MIN_DOMINANCE_RATIO = 0.75

# Minimum keyword length (after normalisation).
MIN_KEYWORD_LENGTH = 4

# Prefer keywords for coverage. Exact merchant entries are only emitted for
# merchants still not covered after keyword coverage reaches this threshold.
TARGET_KEYWORD_COVERAGE = 0.95
MIN_DYNAMIC_KEYWORD_MERCHANTS = 2

# ---------------------------------------------------------------------------
# Stop words: generic location names, state codes, fragments, and other tokens
# that appear across many unrelated merchants and would cause false matches.
# ---------------------------------------------------------------------------
STOP_WORDS: set[str] = {
    # US states / abbreviations / countries
    "calif",
    "texas",
    "york",
    # Cities that appear as location suffixes in merchant names
    "austin",
    "boston",
    "cary",
    "charlotte",
    "chicago",
    "cleveland",
    "cupertino",
    "cupert",
    "cupe",
    "dallas",
    "detroit",
    "durham",
    "fremont",
    "fremon",
    "greensboro",
    "greensb",
    "houston",
    "knoxville",
    "milpitas",
    "morrisville",
    "morris",
    "mountain",
    "nacogdoc",
    "palo",
    "alto",
    "raleigh",
    "redwood",
    "redw",
    "richmond",
    "sacramento",
    "jose",
    "francisco",
    "fransisco",
    "fran",
    "franc",
    "santa",
    "clara",
    "saratoga",
    "seoul",
    "shanghai",
    "singapore",
    "sunnyvale",
    "sunnyval",
    "tokyo",
    "woodside",
    "paris",
    # Generic location/address words
    "street",
    "road",
    "blvd",
    "ave",
    "view",
    "city",
    "north",
    "south",
    "east",
    "west",
    "center",
    "market",
    # Generic business words that appear across many categories
    "store",
    "inc",
    "llc",
    "com",
    "the",
    "and",
    "new",
    "online",
    "payment",
    "paymen",
    "ecomm",
    "egift",
    "egiftrd",
    # State abbreviations and country codes
    "gbr",
    "fra",
    "usa",
    # Fragments from truncated merchant names
    "cupertin",
    "moun",
    "san",
    "del",
    "los",
    # Overly generic words
    "food",
    "home",
    "house",
    "port",
    "bar",
    "grill",
}

DYNAMIC_KEYWORD_STOP_WORDS = STOP_WORDS | {
    "account",
    "ame",
    "aplpay",
    "auarmadale",
    "ca",
    "cruz",
    "dd",
    "de",
    "fee",
    "fr",
    "fra",
    "gglpay",
    "il",
    "iramaint",
    "llc",
    "maintenance",
    "monthly",
    "mountainview",
    "mountainviewca",
    "maria",
    "mntn",
    "ny",
    "ref",
    "restau",
    "san",
    "service",
    "sp",
    "sq",
    "squ",
    "square",
    "store",
    "tn",
    "transfer",
    "tst",
    "tx",
    "va",
    "vcnsantaclar",
    "viewca",
}

# ---------------------------------------------------------------------------
# Brand-name keywords: specific, high-value keywords that should always be
# included even if they appear in only one merchant. These are well-known
# brands/services with unambiguous categories.
# ---------------------------------------------------------------------------
BRAND_KEYWORDS: dict[str, str] = {
    # Transportation / Gas
    "arco": "Transportation",
    "autozone": "Transportation",
    "chevron": "Transportation",
    "chargepoint": "Transportation",
    "fastrak": "Transportation",
    "gasoline": "Transportation",
    "jiffy": "Transportation",
    "lyft": "Transportation",
    "marathon": "Transportation",
    "mbta": "Transportation",
    "mobil": "Transportation",
    "parking": "Transportation",
    "petroleum": "Transportation",
    "quikstop": "Transportation",
    "racetrac": "Transportation",
    "shell": "Transportation",
    "smog": "Transportation",
    "speedway": "Transportation",
    "uber": "Transportation",
    "uhaul": "Transportation",
    "valero": "Transportation",
    "zipcar": "Transportation",
    # Travel
    "airbnb": "Travel",
    "airline": "Travel",
    "airlines": "Travel",
    "avis": "Travel",
    "delta": "Travel",
    "easyjet": "Travel",
    "enterprise": "Travel",
    "eurostar": "Travel",
    "expedia": "Travel",
    "frontier": "Travel",
    "greyhound": "Travel",
    "hertz": "Travel",
    "hotel": "Travel",
    "jetblue": "Travel",
    "marriott": "Travel",
    "megabus": "Travel",
    "norwegian": "Travel",
    "rentacar": "Travel",
    "ryanair": "Travel",
    "sheraton": "Travel",
    "southwest": "Travel",
    "spirit": "Travel",
    "travelocity": "Travel",
    "tripcom": "Travel",
    "united": "Travel",
    "virgin": "Travel",
    "wyndham": "Travel",
    # Groceries
    "bodega": "Groceries",
    "cardenas": "Groceries",
    "costco": "Groceries",
    "grocery": "Groceries",
    "kroger": "Groceries",
    "lucky": "Groceries",
    "publix": "Groceries",
    "safeway": "Groceries",
    "samsclub": "Groceries",
    "sprouts": "Groceries",
    "trader": "Groceries",
    "wholefds": "Groceries",
    # Meal Delivery
    "cerebelly": "Meal Delivery",
    "cookunity": "Meal Delivery",
    "nurture life": "Meal Delivery",
    "thistle": "Meal Delivery",
    # Shopping
    "adidas": "Shopping",
    "amazon": "Shopping",
    "apple": "Shopping",
    "aveda": "Shopping",
    "banana": "Shopping",
    "bestbuy": "Shopping",
    "dollar": "Shopping",
    "dollartree": "Shopping",
    "goodwill": "Shopping",
    "groupon": "Shopping",
    "ikea": "Shopping",
    "jcpenney": "Shopping",
    "lego": "Shopping",
    "lowes": "Shopping",
    "lush": "Shopping",
    "macys": "Shopping",
    "marshalls": "Shopping",
    "mervyns": "Shopping",
    "michaels": "Shopping",
    "nike": "Shopping",
    "oldnavy": "Shopping",
    "oreilly": "Shopping",
    "party": "Shopping",
    "petsmart": "Shopping",
    "ross": "Shopping",
    "saks": "Shopping",
    "sephora": "Shopping",
    "shutterfly": "Shopping",
    "staples": "Shopping",
    "target": "Shopping",
    "tjma": "Shopping",
    "ulta": "Shopping",
    "uniqlo": "Shopping",
    "victorias": "Shopping",
    "walmart": "Shopping",
    "wayfair": "Shopping",
    # Entertainment
    "amc": "Entertainment",
    "audible": "Entertainment",
    "cinema": "Entertainment",
    "cinemark": "Entertainment",
    "disney": "Entertainment",
    "disneyplus": "Entertainment",
    "hulu": "Entertainment",
    "netflix": "Entertainment",
    "peacock": "Entertainment",
    "spotify": "Entertainment",
    "steam": "Entertainment",
    "ticketsatwork": "Entertainment",
    "youtube": "Entertainment",
    "youtubepremium": "Entertainment",
    # Food/Dining Restaurants
    "bbq": "Food/Dining Restaurants",
    "bistro": "Food/Dining Restaurants",
    "bonchon": "Food/Dining Restaurants",
    "burger": "Food/Dining Restaurants",
    "chickfila": "Food/Dining Restaurants",
    "chilis": "Food/Dining Restaurants",
    "chipotle": "Food/Dining Restaurants",
    "chowbus": "Food/Dining Restaurants",
    "cuisine": "Food/Dining Restaurants",
    "deli": "Food/Dining Restaurants",
    "dominos": "Food/Dining Restaurants",
    "doordash": "Food/Dining Restaurants",
    "dumpling": "Food/Dining Restaurants",
    "eatery": "Food/Dining Restaurants",
    "grubhub": "Food/Dining Restaurants",
    "hotpot": "Food/Dining Restaurants",
    "innout": "Food/Dining Restaurants",
    "instacart": "Food/Dining Restaurants",
    "kitchen": "Food/Dining Restaurants",
    "mcdonalds": "Food/Dining Restaurants",
    "noodle": "Food/Dining Restaurants",
    "panda": "Food/Dining Restaurants",
    "panera": "Food/Dining Restaurants",
    "pho": "Food/Dining Restaurants",
    "pizza": "Food/Dining Restaurants",
    "popeyes": "Food/Dining Restaurants",
    "ramen": "Food/Dining Restaurants",
    "restaurant": "Food/Dining Restaurants",
    "sbarro": "Food/Dining Restaurants",
    "subway": "Food/Dining Restaurants",
    "sushi": "Food/Dining Restaurants",
    "taco": "Food/Dining Restaurants",
    "tacos": "Food/Dining Restaurants",
    "taqueria": "Food/Dining Restaurants",
    "tofu": "Food/Dining Restaurants",
    "ubereats": "Food/Dining Restaurants",
    "whataburger": "Food/Dining Restaurants",
    "wingstop": "Food/Dining Restaurants",
    # Food/Dining Coffee/Cafes
    "bakery": "Food/Dining Coffee/Cafes",
    "boba": "Food/Dining Coffee/Cafes",
    "cafe": "Food/Dining Coffee/Cafes",
    "coffee": "Food/Dining Coffee/Cafes",
    "cookies": "Food/Dining Coffee/Cafes",
    "cupcakes": "Food/Dining Coffee/Cafes",
    "donut": "Food/Dining Coffee/Cafes",
    "gelato": "Food/Dining Coffee/Cafes",
    "jamba": "Food/Dining Coffee/Cafes",
    "krispy": "Food/Dining Coffee/Cafes",
    "peets": "Food/Dining Coffee/Cafes",
    "sharetea": "Food/Dining Coffee/Cafes",
    "smoothie": "Food/Dining Coffee/Cafes",
    "sprinkles": "Food/Dining Coffee/Cafes",
    "starbucks": "Food/Dining Coffee/Cafes",
    "sweetgreen": "Food/Dining Coffee/Cafes",
    "tea": "Food/Dining Coffee/Cafes",
    "teaspoon": "Food/Dining Coffee/Cafes",
    "yogurt": "Food/Dining Coffee/Cafes",
    "yogurtland": "Food/Dining Coffee/Cafes",
    # Financial
    "apex": "Financial",
    "atm": "Financial",
    "cashback": "Financial",
    "chase": "Financial",
    "interest": "Financial",
    "investment": "Financial",
    "membership": "Financial",
    "paypal": "Financial",
    "refund": "Financial",
    "robinhood": "Financial",
    "venmo": "Financial",
    "wire": "Financial",
    "withdrawal": "Financial",
    # Healthcare
    "allergy": "Healthcare",
    "asthma": "Healthcare",
    "cvs": "Healthcare",
    "dental": "Healthcare",
    "diagnostics": "Healthcare",
    "healthcare": "Healthcare",
    "medical": "Healthcare",
    "optometry": "Healthcare",
    "pharmacy": "Healthcare",
    "radiology": "Healthcare",
    "riteaid": "Healthcare",
    "walgreen": "Healthcare",
    # Utilities
    "att": "Utilities",
    "comcast": "Utilities",
    "duke": "Utilities",
    "electric": "Utilities",
    "energy": "Utilities",
    "pgande": "Utilities",
    "spectrum": "Utilities",
    "tmobile": "Utilities",
    "verizon": "Utilities",
    # Services/Other
    "cloudflare": "Services/Other",
    "dmv": "Services/Other",
    "docusign": "Services/Other",
    "fedex": "Services/Other",
    "github": "Services/Other",
    "godaddy": "Services/Other",
    "greatclips": "Services/Other",
    "insurance": "Services/Other",
    "namecheap": "Services/Other",
    "squarespace": "Services/Other",
    "supercuts": "Services/Other",
    "usps": "Services/Other",
    # Education
    "college": "Education",
    "exam": "Education",
    "harvard": "Education",
    "leetcode": "Education",
    "stanford": "Education",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_unique_merchants() -> list[str]:
    """Load the unique merchant names from the data file."""
    with open(UNIQUE_MERCHANTS_FILE, "r", encoding="utf-8", newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            has_header = csv.Sniffer().has_header(sample) if sample else False
        except csv.Error:
            has_header = False
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return []

    if has_header:
        header = [cell.strip().lower() for cell in rows[0]]
        merchant_column = header.index("merchant") if "merchant" in header else 0
        data_rows = rows[1:]
    else:
        merchant_column = 0
        data_rows = rows

    merchants = []
    for row in data_rows:
        if merchant_column >= len(row):
            continue
        merchant = row[merchant_column].strip()
        if merchant:
            merchants.append(merchant)
    return merchants


def load_config_map() -> dict[str, str]:
    """Load the existing keyword map from config.yaml."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data: Any = yaml.safe_load(f)
    return data.get("MERCHANT_TO_CATEGORY_MAP", {})


def load_exact_overrides() -> dict[str, str]:
    """Load optional exact merchant overrides for the current merchant set."""
    if not EXACT_OVERRIDES_FILE.exists():
        return {}
    with open(EXACT_OVERRIDES_FILE, "r", encoding="utf-8") as f:
        data: Any = yaml.safe_load(f) or {}
    return data.get("MERCHANT_CATEGORY_OVERRIDES", {})


def normalize(text: str) -> str:
    """Lowercase and strip non-alphanumeric characters."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def tokenize(merchant: str) -> list[str]:
    """Split a merchant name into meaningful tokens."""
    words = re.split(r"[^A-Za-z0-9]+", merchant.lower())
    return [w for w in words if len(w) >= MIN_KEYWORD_LENGTH and w not in STOP_WORDS]


def phrase_tokens(merchant: str) -> list[str]:
    """Return candidate phrase tokens for dynamic keyword generation."""
    return [
        word
        for word in re.split(r"[^A-Za-z0-9]+", merchant.lower())
        if len(word) >= 3 and word not in DYNAMIC_KEYWORD_STOP_WORDS
    ]


def find_keyword_category(merchant: str, keyword_map: dict[str, str]) -> str | None:
    """Return the category found by keyword matching, if any."""
    merchant_norm = normalize(merchant)
    for kw, cat in sorted(
        keyword_map.items(),
        key=lambda item: len(normalize(item[0])),
        reverse=True,
    ):
        if normalize(kw) in merchant_norm:
            return cat
    return None


def build_labeled_merchants(
    merchants: list[str],
    keyword_map: dict[str, str],
    exact_overrides: dict[str, str],
) -> dict[str, str]:
    """Infer a category label for each known merchant."""
    labels: dict[str, str] = {}
    for merchant in merchants:
        exact_cat = exact_overrides.get(merchant)
        keyword_cat = find_keyword_category(merchant, keyword_map)
        if exact_cat:
            labels[merchant] = exact_cat
        elif keyword_cat:
            labels[merchant] = keyword_cat
    return labels


def generate_dynamic_keywords(  # noqa: C901
    keyword_map: dict[str, str],
    merchants: list[str],
    labels: dict[str, str],
) -> dict[str, str]:
    """Add unambiguous merchant-set keywords until target coverage is reached."""
    expanded = dict(keyword_map)
    covered = {
        merchant for merchant in merchants if find_keyword_category(merchant, expanded)
    }

    candidates: dict[str, tuple[str, set[str]]] = {}
    for merchant, category in labels.items():
        tokens = phrase_tokens(merchant)
        phrases: set[str] = set()
        for i in range(len(tokens)):
            for phrase_len in (1, 2, 3):
                if i + phrase_len <= len(tokens):
                    phrase = " ".join(tokens[i : i + phrase_len])
                    if len(normalize(phrase)) >= MIN_KEYWORD_LENGTH:
                        phrases.add(phrase)

        for phrase in phrases:
            phrase_norm = normalize(phrase)
            if phrase_norm in {normalize(kw) for kw in expanded}:
                continue
            matched = {
                known_merchant
                for known_merchant in merchants
                if phrase_norm in normalize(known_merchant)
            }
            if len(matched) < MIN_DYNAMIC_KEYWORD_MERCHANTS:
                continue
            matched_categories = {labels.get(match) for match in matched}
            if (
                matched
                and len(matched_categories) == 1
                and category in matched_categories
            ):
                candidates[phrase] = (category, matched)

    target_count = ceil(len(merchants) * TARGET_KEYWORD_COVERAGE)
    while len(covered) < target_count:
        best: tuple[tuple[int, int], str, str, set[str]] | None = None
        expanded_norms = {normalize(kw) for kw in expanded}
        for phrase, (category, matched) in candidates.items():
            if normalize(phrase) in expanded_norms:
                continue
            gain = len(matched - covered)
            if gain <= 0:
                continue
            score = (gain, len(normalize(phrase)))
            if best is None or score > best[0]:
                best = (score, phrase, category, matched)
        if best is None:
            break

        _score, phrase, category, matched = best
        expanded[phrase] = category
        covered |= matched

    return dict(sorted(expanded.items()))


def minimize_exact_map(
    keyword_map: dict[str, str],
    merchants: list[str],
    exact_overrides: dict[str, str],
) -> dict[str, str]:
    """Keep exact entries only for known merchants not covered by keywords."""
    exact = {}
    for merchant in merchants:
        if (
            merchant in exact_overrides
            and find_keyword_category(merchant, keyword_map) is None
        ):
            exact[merchant] = exact_overrides[merchant]
    return exact


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def generate_keyword_map() -> dict[str, str]:
    """Generate a concise keyword -> category map.

    Strategy:
      1. Start with curated brand keywords (high confidence).
      2. From the proposed exact map, extract tokens and count how often each
         token co-occurs with each category.
      3. Keep only tokens that:
         - appear in >= MIN_MERCHANT_FREQUENCY distinct merchants
         - have a dominant category with >= MIN_DOMINANCE_RATIO
         - are not in the stop-word list
         - are not already covered by a brand keyword
      4. Merge the two sets, with brand keywords taking precedence.
    """
    proposed = load_config_map()

    # Count keyword -> category frequencies
    keyword_cats: dict[str, Counter[str]] = defaultdict(Counter)
    keyword_merchants: dict[str, set[str]] = defaultdict(set)

    for merchant, category in proposed.items():
        for token in tokenize(merchant):
            keyword_cats[token][category] += 1
            keyword_merchants[token].add(merchant)

    # Build the derived keyword map
    derived: dict[str, str] = {}
    for kw, cat_counter in keyword_cats.items():
        total = sum(cat_counter.values())
        if total < MIN_MERCHANT_FREQUENCY:
            continue
        dominant_cat, dominant_count = cat_counter.most_common(1)[0]
        if dominant_count / total < MIN_DOMINANCE_RATIO:
            continue
        # Skip if already a brand keyword
        if kw in BRAND_KEYWORDS:
            continue
        derived[kw] = dominant_cat

    # Merge: existing config and brand keywords take precedence over derived keywords.
    keyword_map = {**derived, **BRAND_KEYWORDS, **load_config_map()}

    # Sort alphabetically for readability
    return dict(sorted(keyword_map.items()))


def compute_coverage(
    keyword_map: dict[str, str],
    merchants: list[str],
    exact_map: dict[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    """Check how many merchants are matched by the keyword map."""
    exact_names = {normalize(merchant) for merchant in (exact_map or {})}
    sorted_keywords = sorted(
        keyword_map.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    matched: list[str] = []
    unmatched: list[str] = []
    for merchant in merchants:
        merchant_norm = normalize(merchant)
        if merchant_norm in exact_names:
            matched.append(merchant)
            continue
        found = False
        for kw, _cat in sorted_keywords:
            if normalize(kw) in merchant_norm:
                found = True
                break
        if found:
            matched.append(merchant)
        else:
            unmatched.append(merchant)
    return matched, unmatched


def format_yaml_map_block(section_name: str, values: dict[str, str]) -> str:
    """Format a top-level string map section for config.yaml."""
    lines = [f"{section_name}:"]
    if not values:
        return f"{section_name}: {{}}"
    for key, cat in values.items():
        key_str = f'"{key}"' if any(ch in key for ch in ":#{}[],&*?|<>=!%@`") else key
        if "/" in cat:
            lines.append(f'  {key_str}: "{cat}"')
        else:
            lines.append(f"  {key_str}: {cat}")
    return "\n".join(lines)


def replace_config_section(
    content: str, section_name: str, values: dict[str, str]
) -> str:
    """Replace or insert a top-level map section in config.yaml."""
    new_block = format_yaml_map_block(section_name, values)
    pattern = rf"^{section_name}:.*?(?=\n[A-Z_]+:|\Z)"
    if re.search(pattern, content, flags=re.DOTALL | re.MULTILINE):
        return re.sub(
            pattern,
            new_block,
            content,
            count=1,
            flags=re.DOTALL | re.MULTILINE,
        )
    return content.rstrip() + "\n" + new_block + "\n"


def write_maps_to_config(
    keyword_map: dict[str, str], exact_map: dict[str, str]
) -> None:
    """Replace category map sections in config.yaml.

    Uses targeted text replacement instead of yaml.safe_dump to preserve
    the original file formatting for all other sections.
    """
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    replaced = replace_config_section(
        content,
        "EXACT_MERCHANT_TO_CATEGORY_MAP",
        dict(sorted(exact_map.items())),
    )
    replaced = replace_config_section(replaced, "MERCHANT_TO_CATEGORY_MAP", keyword_map)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(replaced)


def main() -> None:
    """Entry point."""
    exact_overrides = load_exact_overrides()
    proposed = {**load_config_map(), **exact_overrides}
    merchants = load_unique_merchants()

    print(f"Loaded {len(proposed)} proposed merchant mappings.")
    print(f"Loaded {len(merchants)} unique merchants.")

    keyword_map = generate_keyword_map()
    labels = build_labeled_merchants(merchants, keyword_map, exact_overrides)
    keyword_map = generate_dynamic_keywords(keyword_map, merchants, labels)
    exact_map = minimize_exact_map(keyword_map, merchants, exact_overrides)

    # Count categories
    cats: Counter[str] = Counter(keyword_map.values())
    print(
        f"\nGenerated {len(keyword_map)} keyword entries across {len(cats)} categories:"
    )
    for cat, count in cats.most_common():
        print(f"  {cat}: {count} keywords")

    # Coverage report
    matched, unmatched = compute_coverage(keyword_map, merchants, exact_map)
    pct = len(matched) / len(merchants) * 100 if merchants else 0
    print(f"\nCoverage: {len(matched)}/{len(merchants)} merchants ({pct:.1f}%)")
    if unmatched:
        print(f"\nUnmatched merchants ({len(unmatched)}):")
        for m in sorted(unmatched)[:30]:
            print(f"  - {m}")
        if len(unmatched) > 30:
            print(f"  ... and {len(unmatched) - 30} more")

    # Write to config
    write_maps_to_config(keyword_map, exact_map)
    print(
        f"\nUpdated {CONFIG_FILE.name} with {len(exact_map)} exact merchant entries "
        f"and {len(keyword_map)} keyword entries."
    )


if __name__ == "__main__":
    main()
