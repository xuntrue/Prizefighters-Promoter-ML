import random

import pandas as pd

from . import formatter as fmt

COUNTRY_CODE_COL = "A-2"
COUNTRY_NAME_COL = "CountryName"
FOUNDED_COL = "founded"  # change here if you rename the column to "founded"

def table(df, index=False):
    """Print a DataFrame or Series indented under its subtitle."""
    for row in df.to_string(index=index).splitlines():
        fmt.line(f"  {row}")

# ---------------------------------------------------------------- countries
def analyse_countries(countries):
    fmt.title("COUNTRIES")
    codes = countries[COUNTRY_CODE_COL]
    fmt.line(f"Rows in countries.csv:  {len(countries)}")
    fmt.line(f"Unique country codes:   {codes.nunique()}")

    dupes = codes[codes.duplicated(keep=False)]
    if not dupes.empty:
        fmt.line(f"Duplicate codes: {sorted(dupes.unique())}")

    bad = codes[~codes.str.fullmatch(r"[A-Z]{2}")]
    if not bad.empty:
        fmt.line(f"Codes that aren't two uppercase letters: {sorted(bad.unique())}")

# -------------------------------------------------------------------- flags
def analyse_flags(api, countries):
    fmt.title("COUNTRY FLAGS")
    flag_codes = api.get_flag_codes()
    country_codes = set(countries[COUNTRY_CODE_COL])
    names = countries.set_index(COUNTRY_CODE_COL)[COUNTRY_NAME_COL]

    fmt.line(f"Flag files found: {len(flag_codes)}")

    missing = sorted(country_codes - flag_codes)
    fmt.subtitle(f"Countries without a flag ({len(missing)})")
    for code in missing:
        fmt.line(f"  {code}  {names[code]}")
    if not missing:
        fmt.line("  none")

    orphans = sorted(flag_codes - country_codes)
    if orphans:
        fmt.subtitle(f"Flag files with no matching country ({len(orphans)})")
        fmt.line("  " + ", ".join(orphans))

# ------------------------------------------------------------------- arenas
def analyse_records(arenas, sample_size, seed):
    fmt.title("ARENA RECORDS")
    fmt.line(f"Total arena records: {len(arenas)}")

    fmt.subtitle(f"{sample_size} random records")
    rng = random.Random(seed)
    rows = rng.sample(range(len(arenas)), k=min(sample_size, len(arenas)))  # never repeats
    table(arenas.iloc[rows])

def analyse_country_distribution(arenas, countries):
    fmt.title("ARENAS BY COUNTRY")
    names = countries.set_index(COUNTRY_CODE_COL)[COUNTRY_NAME_COL]
    counts = arenas["country"].value_counts()

    fmt.subtitle("Arena records per country")
    labelled = {f"{code} {names.get(code, '(not in countries.csv)')}": n
                for code, n in counts.items()}
    fmt.histogram(labelled, width=40)

    used = set(arenas["country"])
    known = set(countries[COUNTRY_CODE_COL])

    no_arenas = countries[~countries[COUNTRY_CODE_COL].isin(used)]
    fmt.subtitle(f"Countries in countries.csv with no arenas ({len(no_arenas)})")
    fmt.line("  " + (", ".join(no_arenas[COUNTRY_CODE_COL]) or "none"))

    unknown = sorted(used - known)
    fmt.subtitle(f"Arena countries missing from countries.csv ({len(unknown)})")
    for code in unknown:
        fmt.line(f"  {code}: {counts[code]} arenas")
    if not unknown:
        fmt.line("  none")

def analyse_founded(arenas, n, bin_years):
    fmt.title("YEAR FOUNDED")
    years = arenas[FOUNDED_COL]
    fmt.distribution(years, decimals=0, name="year", thousands=False)

    by_year = arenas.sort_values(FOUNDED_COL)
    fmt.subtitle(f"{n} oldest")
    table(by_year.head(n))
    fmt.subtitle(f"{n} newest")
    table(by_year.tail(n).iloc[::-1])

    start = years.min() // bin_years * bin_years
    end = years.max() // bin_years * bin_years + bin_years
    binned = pd.cut(years, range(start, end + 1, bin_years), right=False)
    counts = binned.value_counts().sort_index()
    fmt.subtitle(f"Arenas founded per {bin_years}-year bin")
    fmt.histogram({f"{b.left}-{b.right - 1}": c for b, c in counts.items()})

def analyse_capacity(arenas, n, min_arenas_per_country):
    fmt.title("CAPACITY")
    fmt.distribution(arenas["capacity"], decimals=0, name="seats")

    fmt.subtitle(f"Top {n} by capacity")
    table(arenas.nlargest(n, "capacity"))
    fmt.subtitle(f"Bottom {n} by capacity")
    table(arenas.nsmallest(n, "capacity"))

    stats = arenas.groupby("country")["capacity"].agg(count="count", mean="mean")
    stats = stats[stats["count"] >= min_arenas_per_country]
    fmt.subtitle(f"Top {n} countries by average capacity (min {min_arenas_per_country} arenas)")
    table(stats.nlargest(n, "mean").round(0).astype(int), index=True)

def analyse_correlation(arenas):
    fmt.title("DO NEWER ARENAS HOLD MORE PEOPLE?")
    pearson = arenas[FOUNDED_COL].corr(arenas["capacity"], method="pearson")
    spearman = arenas[FOUNDED_COL].corr(arenas["capacity"], method="spearman")
    fmt.line(f"Pearson  r   = {pearson:+.3f}  (linear; sensitive to the giant stadiums)")
    fmt.line(f"Spearman rho = {spearman:+.3f}  (rank-based; more robust)")

    decade = (arenas[FOUNDED_COL] // 10 * 10).rename("decade")
    by_decade = arenas.groupby(decade)["capacity"].agg(count="count", median="median", mean="mean")
    fmt.subtitle("Capacity by decade founded")
    table(by_decade.round(0).astype(int), index=True)

    fmt.subtitle("Median capacity by decade")
    fmt.histogram({f"{d}s": int(m) for d, m in by_decade["median"].items()})

    strength = abs(spearman)
    verdict = "weak or no" if strength < 0.2 else "a moderate" if strength < 0.5 else "a strong"
    direction = "positive" if spearman > 0 else "negative"
    fmt.line(f"\nVerdict: {verdict} {direction} relationship between age and capacity.")

# ---------------------------------------------------------------------- run
def run(api, n=10, sample_size=5, bin_years=10, min_arenas_per_country=3, seed=None):
    """Print the full overview. `api` is a PrizeFighterAPI instance."""
    pd.set_option("display.width", 200)

    countries = api.get_countries()
    analyse_countries(countries)
    analyse_flags(api, countries)

    arenas = api.get_arenas()
    analyse_records(arenas, sample_size, seed)
    analyse_country_distribution(arenas, countries)
    analyse_founded(arenas, n, bin_years)
    analyse_capacity(arenas, n, min_arenas_per_country)
    analyse_correlation(arenas)

    return arenas