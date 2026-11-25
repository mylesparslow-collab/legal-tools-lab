"""Small-group suppression.

A privacy choice, not a statistical one: a rate for a group of three people
says too much about each of them. Any cell that describes fewer than
`threshold` people is withheld. Where a published total would let a reader
work out one withheld cell by subtraction, further cells are withheld
(complementary suppression) until at least two cells are hidden and together
they describe at least `threshold` people.
"""

SMALL, COMPLEMENTARY = "small_group", "complementary"


def cell(n, d, people=None):
    """A publishable number: numerator, denominator, people described, rate."""
    people = d if people is None else people
    return {"n": n, "d": d, "people": people, "rate": (n / d) if d else None, "suppressed": None}


def hidden(reason):
    return {"n": None, "d": None, "people": None, "rate": None, "suppressed": reason}


def suppress_cells(cells, threshold, total_published=True):
    """Apply primary and complementary suppression to one column of cells.

    cells is a list of cell dicts that partition a published total. Returns a
    new list. Empty cells (no people) are left as they are: there is nobody to
    protect and they do not help hide anyone else.
    """
    out = [dict(c) for c in cells]
    sizes = [c["people"] or 0 for c in cells]
    marks = {}
    for i, size in enumerate(sizes):
        if 0 < size < threshold:
            marks[i] = SMALL
    if marks and total_published:
        while len(marks) < 2 or sum(sizes[i] for i in marks) < threshold:
            rest = [i for i, s in enumerate(sizes) if i not in marks and s > 0]
            if not rest:
                break
            marks[min(rest, key=lambda i: (sizes[i], i))] = COMPLEMENTARY
    for i, reason in marks.items():
        out[i] = hidden(reason)
    return out


def suppress_counts(counts, threshold, partition):
    """Suppress small counts in a tally of survey answers.

    counts maps option -> number of people. Returns option -> number or None.
    For a single-choice question (partition=True) the options add up to the
    number of respondents, so complementary suppression applies as well.
    """
    keys = list(counts)
    cells = suppress_cells([cell(counts[k], counts[k]) for k in keys], threshold, total_published=partition)
    return {k: (None if c["suppressed"] else c["n"]) for k, c in zip(keys, cells)}
