import random

import pandas as pd

COUNTRY_CODE_COL = "A-2"
COUNTRY_NAME_COL = "CountryName"
FOUNDED_COL = "founded"  # change here if you rename the column to "founded"

def section(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")

# ---------------------------------------------------------------- countries
def analyse_countries(countries):
    section("1. COUNTRIES")
    codes = countries[COUNTRY_CODE_COL]
    print(f"Rows in countries.csv:  {len(countries)}")
    print(f"Unique country codes:   {codes.nunique()}")

    dupes = codes[codes.duplicated(keep=False)]
    if not dupes.empty:
        print(f"Duplicate codes: {sorted(dupes.unique())}")

    bad = codes[~codes.str.fullmatch(r"[A-Z]{2}")]
    if not bad.empty:
        print(f"Codes that aren't two uppercase letters: {sorted(bad.unique())}")

# -------------------------------------------------------------------- flags
def analyse_flags(api, countries):
    section("2. COUNTRY FLAGS")
    flag_codes = api.get_flag_codes()
    country_codes = set(countries[COUNTRY_CODE_COL])

    print(f"Flag files found: {len(flag_codes)}")

    missing = sorted(country_codes - flag_codes)
    print(f"Countries without a flag: {len(missing)}")
    for code in missing:
        name = countries.loc[countries[COUNTRY_CODE_COL] == code, COUNTRY_NAME_COL].iloc[0]
        print(f"  {code}  {name}")

    orphans = sorted(flag_codes - country_codes)
    if orphans:
        print(f"Flag files with no matching country: {orphans}")

# ------------------------------------------------------------------- arenas
def show_records(arenas, n, seed):
    print(f"\n{n} random records:")
    rng = random.Random(seed)
    rows = rng.sample(range(len(arenas)), k=min(n, len(arenas)))  # sample() never repeats
    print(arenas.iloc[rows].to_string(index=False))

def analyse_country_distribution(arenas, countries):
    section("4. ARENAS BY COUNTRY")
    names = countries.set_index(COUNTRY_CODE_COL)[COUNTRY_NAME_COL]
    counts = arenas["country"].value_counts().rename("arenas").to_frame()
    counts.insert(0, "name", counts.index.map(names).fillna("(not in countries.csv)"))
    print(counts.to_string())

    used = set(arenas["country"])
    known = set(countries[COUNTRY_CODE_COL])

    no_arenas = countries[~countries[COUNTRY_CODE_COL].isin(used)]
    print(f"\nCountries in countries.csv with no arenas: {len(no_arenas)}")
    print(", ".join(no_arenas[COUNTRY_CODE_COL]) or "  none")

    unknown = sorted(used - known)
    print(f"\nArena countries missing from countries.csv: {len(unknown)}")
    for code in unknown:
        print(f"  {code}: {(arenas['country'] == code).sum()} arenas")

def analyse_founded(arenas, bin_years):
    section("5. YEAR FOUNDED")
    by_year = arenas.sort_values(FOUNDED_COL)
    print("Oldest:")
    print(by_year.head(5).to_string(index=False))
    print("\nNewest:")
    print(by_year.tail(5).iloc[::-1].to_string(index=False))

    years = arenas[FOUNDED_COL]
    start = years.min() // bin_years * bin_years
    end = years.max() // bin_years * bin_years + bin_years
    bins = range(start, end + 1, bin_years)
    counts = pd.cut(years, bins, right=False).value_counts().sort_index()

    print(f"\nArenas founded per {bin_years}-year bin:")
    scale = 50 / counts.max()
    for interval, count in counts.items():
        label = f"{interval.left}-{interval.right - 1}"
        print(f"  {label}  {'#' * round(count * scale):<50} {count}")

def analyse_capacity(arenas, n, min_arenas_per_country):
    section("6. CAPACITY")
    print(arenas["capacity"].describe().round(1).to_string())

    print(f"\nTop {n} by capacity:")
    print(arenas.nlargest(n, "capacity").to_string(index=False))
    print(f"\nBottom {n} by capacity:")
    print(arenas.nsmallest(n, "capacity").to_string(index=False))

    stats = arenas.groupby("country")["capacity"].agg(count="count", mean="mean")
    stats = stats[stats["count"] >= min_arenas_per_country]
    print(f"\nTop {n} countries by average capacity "
          f"(countries with at least {min_arenas_per_country} arenas):")
    print(stats.nlargest(n, "mean").round(0).astype(int).to_string())

def analyse_correlation(arenas):
    section("7. DO NEWER ARENAS HOLD MORE PEOPLE?")
    pearson = arenas[FOUNDED_COL].corr(arenas["capacity"], method="pearson")
    spearman = arenas[FOUNDED_COL].corr(arenas["capacity"], method="spearman")
    print(f"Pearson  r   = {pearson:+.3f}  (linear; sensitive to the giant stadiums)")
    print(f"Spearman rho = {spearman:+.3f}  (rank-based; more robust)")

    decade = (arenas[FOUNDED_COL] // 10 * 10).rename("decade")
    table = arenas.groupby(decade)["capacity"].agg(count="count", median="median", mean="mean")
    print("\nCapacity by decade founded:")
    print(table.round(0).astype(int).to_string())

    strength = abs(spearman)
    verdict = "weak or no" if strength < 0.2 else "a moderate" if strength < 0.5 else "a strong"
    direction = "positive" if spearman > 0 else "negative"
    print(f"\nVerdict: {verdict} {direction} relationship between age and capacity.")

def analyse_arenas(api, countries, n=10, sample_size=5, bin_years=10,
                   min_arenas_per_country=3, seed=None):
    arenas = api.get_arenas()

    section("3. ARENA RECORDS")
    print(f"Total arena records: {len(arenas)}")
    show_records(arenas, sample_size, seed)

    analyse_country_distribution(arenas, countries)
    analyse_founded(arenas, bin_years)
    analyse_capacity(arenas, n, min_arenas_per_country)
    analyse_correlation(arenas)
    return arenas

def run(api, **options):
    """Print the full overview. `api` is a PrizeFighterAPI instance."""
    pd.set_option("display.width", 200)
    countries = api.get_countries()
    analyse_countries(countries)
    analyse_flags(api, countries)
    return analyse_arenas(api, countries, **options)