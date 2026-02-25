import os
from dotenv import load_dotenv
import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
from collections.abc import Iterable
import pandas as pd
from sqlalchemy import create_engine

load_dotenv()

engine = create_engine(os.getenv("SQL_CONNECTION"))
_DATA_CACHE = None

def get_data(project_privacy=False):
  global _DATA_CACHE
  # Load data once
  if _DATA_CACHE is None:
    _DATA_CACHE = pd.read_sql_table("app_data", con=engine)

  df = _DATA_CACHE  # start from cached data

  # Apply privacy filter if requested
  if project_privacy:
    col = 'anonymous_status'
    df = df[df[col] != 'anon']

  return df.copy()  


##### TO REMOVE LIST FORMAT FOR PROJECT CARDS AND PRINTING OUT DATA
def add_formatted_list_columns(
  df: pd.DataFrame,
  cols: Iterable[str] | str,
  suffix: str = "_formatted",
  inplace: bool = True,
):
  """
  For each column in `cols`, clean list-like strings (e.g., "['A','B']" -> "A, B")
  and insert a new column <col><suffix> immediately after the source column.

  If inplace=False, returns a dict {new_col: cleaned_series} without inserting.
  """
  # normalize cols to a list
  if isinstance(cols, str):
    cols = [cols]
  else:
    cols = list(cols)

  # sanity check
  missing = [c for c in cols if c not in df.columns]
  if missing:
    raise KeyError(f"Column(s) not found: {missing}")

  def _clean(series: pd.Series) -> pd.Series:
    return (
      series.where(series.notna(), "")
        .astype(str)
        .str.strip("[]")
        .str.replace("'", "", regex=False)
        .str.replace('"', "", regex=False)
        .str.replace(r"\s*,\s*", ", ", regex=True)
        .str.strip()
    )
  if not inplace:
    return {f"{c}{suffix}": _clean(df[c]) for c in cols}

  # insert each cleaned column right after its source (recompute index each time)
  for c in cols:
    cleaned = _clean(df[c])
    insert_at = df.columns.get_loc(c) + 1
    df.insert(insert_at, f"{c}{suffix}", cleaned)

  return df


def format_number_column(df: pd.DataFrame, col: str, decimals: int = 0, new_col: str | None = None):
  fmt = f"{{:,.{decimals}f}}"
  formatted = df[col].apply(lambda x: "" if pd.isna(x) else fmt.format(float(x)))

  if new_col:
    df.insert(df.columns.get_loc(col) + 1, new_col, formatted)
  else:
    df[col] = formatted
  return df



