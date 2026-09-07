"""
element_fraction_table.py

Reshapes the compositions table (long format: one row per sample-
element pair) into the wide format needed for ML (one row per sample,
one column per element) -- a standard "composition vector"
representation.

Deliberately NOT a new physical database table: a wide table would need
a schema change (ALTER TABLE ADD COLUMN) every time a new element
appears in a future sample, and would be mostly empty cells for any
given row (most samples use a small fraction of the periodic table).
Since the actual consumer of this data is Python/ML tooling (per this
project's own stated goal), reshaping on demand avoids that churn
entirely -- add a new element to a new sample's rows in `compositions`
and this function picks it up automatically, no migration needed.

Uses atomic_percent as the value by default (confirmed as the primary
representation needed for this project -- weight_percent is described
as only needed for rare/extreme cases). Missing elements for a given
sample are filled with 0 (a sample genuinely containing 0% of an
element is different from "unknown" -- there is no NULL case here,
since every element either appears in a sample's composition rows or
it doesn't).
"""

import pandas as pd


def get_element_fraction_table(conn, fraction_column='atomic_percent',
                                include_sample_id_string=True):
    """
    Queries the compositions table and returns a wide-format pandas
    DataFrame: one row per sample, one column per element.

    conn: a live psycopg2 (or DBAPI2-compatible) connection.
    fraction_column: 'atomic_percent' (default) or 'weight_percent'.
    include_sample_id_string: if True, joins against the samples table
        to include the human-readable sample_id (e.g. 'HD335') alongside
        the raw integer id -- much more usable than bare integer ids
        alone when reviewing this table directly.

    Returns a DataFrame indexed by the integer sample id, with one
    column per element seen ANYWHERE in the compositions table (not
    just for this specific sample), zero-filled for elements a given
    sample doesn't contain.
    """
    if fraction_column not in ('atomic_percent', 'weight_percent'):
        raise ValueError(f"fraction_column must be 'atomic_percent' or 'weight_percent'; got {fraction_column!r}")

    query = f"""
        SELECT sample_id, element, {fraction_column}
        FROM compositions
        WHERE {fraction_column} IS NOT NULL
    """
    long_df = pd.read_sql(query, conn)

    if long_df.empty:
        raise ValueError(
            f"No rows found with a non-null {fraction_column} -- nothing to reshape. "
            f"If using atomic_percent, has it been populated yet (see compute_atomic_percent.py)?"
        )

    wide_df = long_df.pivot(index='sample_id', columns='element', values=fraction_column)
    wide_df = wide_df.fillna(0.0)  # a sample not containing an element genuinely has 0% of it

    if include_sample_id_string:
        sample_names = pd.read_sql("SELECT id, sample_id FROM samples", conn)
        sample_names = sample_names.set_index('id')['sample_id']
        wide_df.insert(0, 'sample_id_string', wide_df.index.map(sample_names))

    return wide_df


def export_to_csv(conn, output_path, fraction_column='atomic_percent'):
    """Convenience wrapper: builds the wide table and saves it as CSV --
    a simple, universal way to hand this data to any ML tool regardless
    of language/library."""
    df = get_element_fraction_table(conn, fraction_column=fraction_column)
    df.to_csv(output_path)
    return df
