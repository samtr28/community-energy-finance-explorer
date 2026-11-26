import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
from .Global_Server_Functions import get_data
from .filter_config import FILTERS


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