import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import plotly.graph_objects as go
from .Global_Server_Functions import get_data
from .filter_config import (FILTERS, MIN_RESPONSES_SHOWN,
                            ANON_COLUMN, ANON_VALUE, MESSAGES)

def count_responses(df):
  """Number of distinct survey responses (record_id) in a dataframe."""
  if df is None or df.empty or 'record_id' not in df.columns:
    return 0
  return int(df['record_id'].nunique())


def count_projects(df):
  """
  Number of projects, using the same figure as the Overview page:
  the num_projects_response column, summed once per survey response.
  Falls back to counting sub_projects (or 1) only for a record with no value.
  """
  if df is None or df.empty or 'record_id' not in df.columns:
    return 0
  records = df.drop_duplicates('record_id')

  def per_record(row):
    n = row.get('num_projects_response') if 'num_projects_response' in records.columns else None
    try:
      if n is not None and n == n and n > 0:      # n == n filters out NaN
        return int(n)
    except TypeError:
      pass
    s = row.get('sub_projects') if 'sub_projects' in records.columns else None
    return len(s) if isinstance(s, list) and len(s) > 0 else 1

  return int(sum(per_record(r) for _, r in records.iterrows()))
  

def apply_filters(df, filters):
  """
  Apply every selected filter in FILTERS to a dataframe. Returns a filtered copy.
  `filters` is a dict like {'provinces': ['Alberta'], 'owner_categories': ['Indigenous']}.
  Empty or missing keys are ignored. Raises a clear error if a frame lacks a needed column.
  """
  if df.empty or not filters:
    return df
  df = df.copy()
  for spec in FILTERS:
    selected = filters.get(spec['key'])
    if not selected:
      continue
    col = spec['column']
    if col not in df.columns:
      raise KeyError(f"Filter '{spec['key']}' needs column '{col}', which this dataframe does not have.")
    if spec['kind'] == 'in':
      df = df[df[col].isin(selected)]
    else:
      df = df[df[col].apply(
        lambda x: any(v in x for v in selected) if isinstance(x, list) else False
      )]
  return df


@anvil.server.callable
def get_owner_type_options():
  """{owner_category: [owner_type, ...]} built from the data (labels only)."""
  options = {}
  for owners in get_data()['owners']:
    if not isinstance(owners, list):
      continue
    for o in owners:
      if not isinstance(o, dict):
        continue
      cat = str(o.get('owner_category') or 'Other / Unknown').strip()
      typ = o.get('owner_type')
      options.setdefault(cat, set())
      if typ:
        options[cat].add(str(typ).strip())
  return {c: sorted(t) for c, t in options.items()}


@anvil.server.callable
def get_filter_options(project_privacy=False):
  """{filter_key: [values in the data]} for filters whose items come from the data."""
  df = get_data(project_privacy=project_privacy)
  options = {}
  for spec in FILTERS:
    if spec.get('items_from') != 'data':
      continue
    col = spec['column']
    if col not in df.columns:
      continue
    values = set()
    for v in df[col].dropna():
      for item in (v if isinstance(v, list) else [v]):
        if item not in (None, ''):
          values.add(item)
    options[spec['key']] = sorted(values, key=lambda s: str(s).lower())
  return options

def apply_privacy(df_raw, filters):
  """
  Privacy rule for any page. Call this first, then build the page's own
  frames from the returned df_raw.

  If fewer than MIN_RESPONSES_SHOWN survey responses match and an anonymous
  one is among them, anonymous projects are removed from the data.

  Returns (df_raw, df_filtered, summary):
    df_raw       raw data to build the page's frames from (anonymous removed if needed)
    df_filtered  df_raw with the filters applied
    summary      {'project_count', 'total_projects', 'no_results', 'anon_excluded'}
  """
  n_total     = count_projects(df_raw)
  anon_ids    = set(df_raw.loc[df_raw[ANON_COLUMN] == ANON_VALUE, 'record_id'])
  df_filtered = apply_filters(df_raw, filters)

  small_with_anon = (count_responses(df_filtered) < MIN_RESPONSES_SHOWN
                     and bool(set(df_filtered['record_id']) & anon_ids))
  if small_with_anon:
    df_raw      = df_raw[~df_raw['record_id'].isin(anon_ids)]
    df_filtered = apply_filters(df_raw, filters)

  no_results = count_responses(df_filtered) == 0
  summary = {
    'project_count':  count_projects(df_filtered),
    'total_projects': n_total,
    'no_results':     no_results,
    'anon_excluded':  small_with_anon and not no_results,
  }
  return df_raw, df_filtered, summary


def blank_result(chart_keys, summary):
  """Empty figures plus the standard 'nothing to show' summary."""
  fig = go.Figure()
  fig.update_layout(title=dict(text=MESSAGES['hidden']))
  result = {k: fig for k in chart_keys}
  result.update(project_count=0, total_projects=summary['total_projects'],
                no_results=True, anon_excluded=False)
  return result