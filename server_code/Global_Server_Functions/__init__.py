import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
from collections.abc import Iterable
import pandas as pd
from .config import brand_template
import plotly.io as pio
import base64
import plotly.graph_objects as go


_DATA_CACHE = None

def get_data(project_privacy=False):
  global _DATA_CACHE
  # Load data once
  if _DATA_CACHE is None:
    _DATA_CACHE = pd.read_pickle(data_files['synthetic_data.pkl'])

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

def _register_brand_template():
  with open(data_files['UVic_logo.png'], 'rb') as f:
    encoded = base64.b64encode(f.read()).decode('utf-8')
  logo_uri = f"data:image/png;base64,{encoded}"
  brand_template.layout.images[0]['source'] = logo_uri
  pio.templates["my_brand"] = brand_template

# Runs once when the module loads
_register_brand_template()


@anvil.server.callable
def download_chart(fig_dict, active_filters: dict, filename: str = "chart"):
  fig = go.Figure(fig_dict)

  # Build filter annotation text
  filter_parts = []
  label_map = {
    'provinces': 'Province',
    'proj_types': 'Project Type',
    'stages': 'Stage',
    'indigenous_ownership': 'Indigenous Ownership',
    'project_scale': 'Project Scale'
  }
  for key, label in label_map.items():
    values = active_filters.get(key)
    if values:
      filter_parts.append(f"<b>{label}:</b> {', '.join(values)}")

  filter_text = "  |  ".join(filter_parts) if filter_parts else "No filters applied"

  fig.update_layout(
    template="my_brand",
    paper_bgcolor='white',
    plot_bgcolor='white',
    margin=dict(l=20, r=20, t=80, b=60)
  )

  fig.add_annotation(
    text=filter_text,
    xref="paper", yref="paper",
    x=0.0, y=-0.08,
    showarrow=False,
    font=dict(size=10, color="gray", family="Arial, sans-serif"),
    align="left",
    xanchor="left"
  )

  img_bytes = pio.to_image(fig, format="png", width=1400, height=700)
  return anvil.BlobMedia("image/png", img_bytes, name=f"{filename}.png")