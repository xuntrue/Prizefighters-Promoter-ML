def title(title: str):
    print(f"\n{'=' * 30} {title} {'=' * 30}")

def subtitle(subtitle: str):
    print(f"\n{'-' * 10} {subtitle} {'-' * 10}")

def line(text=""):
    print(text)

def histogram(counts, width: int = 50, symbol: str = "#"):
    """ Displays a histogram visual in the terminal """
    items = [(str(label), int(count)) for label, count in counts.items()]
    if not items:
        line("  (no data)")
        return

    label_width = max(len(label) for label, _ in items)
    count_width = len(str(max(count for _, count in items)))
    largest = max(count for _, count in items) or 1

    for label, count in items:
        bar = symbol * round(count / largest * width)
        line(f"  {label:>{label_width}} | {bar:<{width}} {count:>{count_width}}")


def distribution(values, decimals: int = 1, name: str = "", thousands: bool = True):
    """ Very similar to .describe(), but prints in a horizontal fashion to take up less space vertically """
    sep = "," if thousands else ""
    stats = values.describe()
    labels = ["count", "mean", "std", "min", "25%", "50%", "75%", "max"]
    cells = [f"{int(stats['count'])}"] + [f"{stats[k]:{sep}.{decimals}f}" for k in labels[1:]]
    widths = [max(len(label), len(cell)) for label, cell in zip(labels, cells)]

    prefix = f"  {name:<{len(name)}}  " if name else "  "
    blank = " " * len(prefix)
    line(blank + "  ".join(label.rjust(w) for label, w in zip(labels, widths)))
    line(prefix + "  ".join(cell.rjust(w) for cell, w in zip(cells, widths)))