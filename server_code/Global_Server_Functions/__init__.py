import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
from collections.abc import Iterable
import pandas as pd
import base64
import copy
import anvil.media


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

# ---------- Shared helpers (write once, reuse for every chart) ----------

def _load_logo_datauri(filename='logo.png'):
  """Read the logo from data files and return a data: URI Plotly can embed."""
  try:
    with open(data_files[filename], 'rb') as f:
      b64 = base64.b64encode(f.read()).decode('ascii')
    return f"data:image/png;base64,{b64}"
  except Exception:
    return None

def build_filter_summary(provinces=None, proj_types=None, stages=None,
                         indigenous_ownership=None, project_scale=None):
  """Produce a single HTML-ish string summarizing active filters for the header."""
  parts = []
  if provinces:
    parts.append(f"<b>Provinces:</b> {', '.join(provinces)}")
  if proj_types:
    parts.append(f"<b>Project types:</b> {', '.join(proj_types)}")
  if stages:
    parts.append(f"<b>Stages:</b> {', '.join(stages)}")
  if indigenous_ownership:
    parts.append(f"<b>Indigenous ownership:</b> {', '.join(indigenous_ownership)}")
  if project_scale:
    parts.append(f"<b>Project scale:</b> {', '.join(project_scale)}")
  if not parts:
    return "<i>No filters applied — all projects included</i>"
  return "  &nbsp;•&nbsp;  ".join(parts)

def decorate_for_download(fig, chart_title, filter_summary,
                          width=1600, height=1000, logo_filename='logo.png'):
  """
    Take any Plotly figure and return a *copy* dressed up for a branded export:
      - bigger canvas
      - title + filter summary at the top
      - logo bottom-right
      - footer text bottom-left
    Does not mutate the original figure.
    """
  fig = copy.deepcopy(fig)
  logo_src = _load_logo_datauri(logo_filename)

  # Make room at the top (title + filters) and bottom (logo + footer)
  fig.update_layout(
    width=width,
    height=height,
    paper_bgcolor='white',
    plot_bgcolor='white',
    margin=dict(l=60, r=60, t=180, b=140),
    title=dict(
      text=(
        f"<b style='font-size:22px'>{chart_title}</b>"
        f"<br><span style='font-size:13px;color:#555'>{filter_summary}</span>"
      ),
      x=0.02, xanchor='left',
      y=0.97, yanchor='top',
      font=dict(family='Arial, sans-serif', color='black'),
    ),
  )

  # Footer text (bottom-left)
  fig.add_annotation(
    text="<i>Capital Explorer — generated with the filters shown above</i>",
    xref='paper', yref='paper',
    x=0.0, y=-0.11,
    xanchor='left', yanchor='top',
    showarrow=False,
    font=dict(size=11, color='#777', family='Arial, sans-serif'),
  )

  # Logo (bottom-right). Merge with any existing layout.images rather than overwrite.
  if logo_src:
    existing = list(fig.layout.images) if fig.layout.images else []
    existing.append(dict(
      source=logo_src,
      xref='paper', yref='paper',
      x=1.0, y=-0.04,
      sizex=0.14, sizey=0.14,
      xanchor='right', yanchor='top',
      layer='above',
    ))
    fig.update_layout(images=existing)

  return fig

def figure_to_media(fig, filename_base, fmt='png', scale=2):
  """Export a figure to bytes and wrap it as an anvil.BlobMedia for download."""
  img_bytes = fig.to_image(format=fmt, scale=scale)  # width/height come from layout
  mime = {
    'png':  'image/png',
    'jpeg': 'image/jpeg',
    'svg':  'image/svg+xml',
    'pdf':  'application/pdf',
  }.get(fmt, 'application/octet-stream')
  return anvil.BlobMedia(mime, img_bytes, name=f"{filename_base}.{fmt}")



