import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import pandas as pd
import numpy as np
import ast
import plotly.express as px
import plotly.graph_objects as go
from collections.abc import Iterable
from .Global_Server_Functions import add_formatted_list_columns, format_number_column, get_data
from .config import COLOUR_MAPPING, gradient_palette, dunsparce_colors


# ============= COLOR PALETTE CONFIGURATION =============
def create_palette_from_hex(hex_color, num_shades=5):
  """Create a palette of shades from a base hex color"""
  hex_color = hex_color.lstrip('#')
  r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)

  palette = []
  for i in range(num_shades):
    blend = i * 0.15
    new_r = int(r + (255 - r) * blend)
    new_g = int(g + (255 - g) * blend)
    new_b = int(b + (255 - b) * blend)
    palette.append(f'#{new_r:02x}{new_g:02x}{new_b:02x}')

  return palette


# Base colors from config
BASE_COLORS = {
  'Grants': COLOUR_MAPPING['Grants'],
  'Equity': COLOUR_MAPPING['Equity'],
  'Debt': COLOUR_MAPPING['Debt'],
  'Crowdfund': COLOUR_MAPPING['Crowdfund'],
  'Internal capital': COLOUR_MAPPING['Internal capital'],
  'Community finance': COLOUR_MAPPING['Community finance'],
}

CATEGORY_PALETTES = {
  'Grants': create_palette_from_hex(BASE_COLORS['Grants']),
  'Equity': create_palette_from_hex(BASE_COLORS['Equity']),
  'Debt': create_palette_from_hex(BASE_COLORS['Debt']),
  'Crowdfund': create_palette_from_hex(BASE_COLORS['Crowdfund']),
  'Internal capital': create_palette_from_hex(BASE_COLORS['Internal capital']),
  'Community finance': create_palette_from_hex(BASE_COLORS['Community finance']),
  'Unknown': ['#4A5568', '#718096', '#A0AEC0', '#CBD5E0', '#E2E8F0']
}

DEFAULT_PALETTE = ['#7f7f7f', '#a0a0a0', '#c0c0c0', '#d9d9d9', '#efefef']

OWNERSHIP_COLORS = gradient_palette[::-1]


# ============= DATA LOADING =============
DATA = get_data(project_privacy=True)


# ============= HELPER FUNCTIONS =============
def _ensure_sub_projects_list(val):
  """Safely convert sub_projects value to a list of dicts.
  Handles: list, NaN, None, string representation of list."""
  if val is None:
    return []
  if isinstance(val, float) and pd.isna(val):
    return []
  if isinstance(val, str):
    try:
      parsed = ast.literal_eval(val)
      if isinstance(parsed, list):
        return parsed
    except Exception:
      return []
  if isinstance(val, list):
    return val
  return []


def build_ownership_bar(owners, ownership_colors):
  """Build bar traces for ownership data. Returns list of go.Bar traces."""
  if owners is None:
    return []
  elif isinstance(owners, dict):
    owners = [owners]
  elif not isinstance(owners, (list, tuple)):
    return []

  bars = []
  for i, o in enumerate(owners):
    if not isinstance(o, dict):
      continue

    name = o.get('owner_name', '')
    owner_type = o.get('owner_type', '')
    try:
      pct = float(o.get('owner_percent', 0) or 0)
    except Exception:
      pct = 0.0

    color = ownership_colors[i % len(ownership_colors)]

    bars.append(
      go.Bar(
        x=[pct],
        y=[''],
        name=name,
        orientation='h',
        marker_color=color,
        customdata=[[name, owner_type]],
      )
    )

  return bars


def build_capital_mix_traces(capital_mix, category_palettes):
  """Build bar traces for a single capital mix entry. Returns list of go.Bar traces."""
  if capital_mix is None:
    return []
  elif isinstance(capital_mix, dict):
    capital_mix = [capital_mix]
  elif not isinstance(capital_mix, (list, tuple)):
    return []

  mix_df = pd.DataFrame(capital_mix)

  if mix_df.empty:
    return []

  mix_df["name"] = mix_df["name"].astype(str).replace({"nan": "Unnamed"})
  mix_df["category"] = mix_df["category"].astype(str).fillna("Unknown")
  mix_df["percent"] = pd.to_numeric(mix_df["percent"], errors='coerce').fillna(0)
  mix_df["amount"] = pd.to_numeric(mix_df["amount"], errors='coerce').fillna(0)
  mix_df["item_type"] = mix_df.get("item_type", "").astype(str)
  mix_df["row"] = ""

  total_percent = mix_df["percent"].sum()
  total_amount = mix_df["amount"].sum()
  difference = 100 - total_percent

  if abs(difference) <= 7.5:
    if total_percent > 0:
      mix_df["display_percent"] = (mix_df["percent"] / total_percent) * 100
    else:
      mix_df["display_percent"] = 0
  elif difference > 7.5:
    mix_df["display_percent"] = mix_df["percent"]
    if total_amount > 0 and total_percent > 0:
      unknown_amount = (difference / total_percent) * total_amount
    else:
      unknown_amount = 0
    unknown_row = pd.DataFrame({
      "name": ["Unknown"],
      "category": ["Unknown"],
      "percent": [difference],
      "amount": [unknown_amount],
      "item_type": ["Unknown"],
      "row": [""],
      "display_percent": [difference]
    })
    mix_df = pd.concat([unknown_row, mix_df], ignore_index=True)
  else:
    mix_df["display_percent"] = mix_df["percent"]

  traces = []
  for cat, group in mix_df.groupby("category", sort=False):
    palette = category_palettes.get(cat, DEFAULT_PALETTE)
    for i, row in enumerate(group.itertuples()):
      traces.append(
        go.Bar(
          x=[row.display_percent],
          y=[row.row],
          name=cat,
          marker_color=palette[i % len(palette)],
          legendgroup=cat,
          showlegend=(i == 0),
          orientation="h",
          customdata=[[row.category, row.item_type, row.name,
                       row.percent, row.amount]],
          text=f"{row.display_percent:.0f}%" if row.display_percent > 5 else "",
          textposition="inside",
          textfont=dict(size=10),
          hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Type: %{customdata[1]}<br>"
            "Name: %{customdata[2]}<br>"
            "Percent: %{customdata[3]:.1f}%<br>"
            "Amount: $%{customdata[4]:,.0f}"
            "<extra></extra>"
          ),
        )
      )

  return traces


# ============= PORTFOLIO / SUB-PROJECT HELPERS =============
def explode_for_map(df):
  """Expand portfolios into one map point per sub-project location.
  Standalone projects pass through as a single point."""
  rows = []

  has_subs = "sub_projects" in df.columns

  for _, row in df.iterrows():
    subs = _ensure_sub_projects_list(row.get("sub_projects")) if has_subs else []

    if len(subs) > 0:
      for sub in subs:
        lat = sub.get("latitude")
        lon = sub.get("longitude")
        if lat is None or lon is None:
          continue
        try:
          lat = float(lat)
          lon = float(lon)
        except (ValueError, TypeError):
          continue
        rows.append({
          "record_id": row["record_id"],
          "project_name": f"{row['project_name']} — {sub.get('site_name', '')}",
          "community": sub.get("community", ""),
          "latitude": lat,
          "longitude": lon,
        })
    else:
      # Standalone project
      lat = row.get("latitude")
      lon = row.get("longitude")
      if pd.notna(lat) and pd.notna(lon):
        rows.append({
          "record_id": row["record_id"],
          "project_name": row["project_name"],
          "community": row.get("community", ""),
          "latitude": float(lat),
          "longitude": float(lon),
        })

  if rows:
    return pd.DataFrame(rows)
  else:
    return pd.DataFrame(columns=["record_id", "project_name", "community", "latitude", "longitude"])


def apply_filters(df, provinces=None, proj_types=None, stages=None,
                  indigenous_ownership=None, project_scale=None):
  """Apply filters to dataframe. Returns filtered copy."""
  df = df.copy()

  has_subs = "sub_projects" in df.columns

  if provinces:
    if has_subs:
      def province_match(row):
        if row["province"] in provinces:
          return True
        for s in _ensure_sub_projects_list(row.get("sub_projects")):
          if s.get("province") in provinces:
            return True
        return False
      df = df[df.apply(province_match, axis=1)]
    else:
      df = df[df["province"].isin(provinces)]

  if proj_types:
    if has_subs:
      def type_match(row):
        parent_types = row.get("project_type", [])
        if isinstance(parent_types, list) and any(t in parent_types for t in proj_types):
          return True
        for s in _ensure_sub_projects_list(row.get("sub_projects")):
          if s.get("project_type") in proj_types:
            return True
        return False
      df = df[df.apply(type_match, axis=1)]
    else:
      df = df[df["project_type"].apply(lambda lst: any(t in lst for t in proj_types))]

  if stages:
    if has_subs:
      def stage_match(row):
        if row["stage"] in stages:
          return True
        for s in _ensure_sub_projects_list(row.get("sub_projects")):
          if s.get("stage") in stages:
            return True
        return False
      df = df[df.apply(stage_match, axis=1)]
    else:
      df = df[df["stage"].isin(stages)]

  if indigenous_ownership:
    df = df[df["indigenous_ownership"].isin(indigenous_ownership)]

  if project_scale:
    df = df[df["project_scale"].isin(project_scale)]

  return df


def get_map_data_internal(df):
  """Create map trace. Uses SAME customdata format as the original."""
  if df.empty:
    return go.Scattermap(lat=[], lon=[], mode='markers')

  map_data = go.Scattermap(
    lat=df['latitude'],
    lon=df['longitude'],
    mode='markers',
    text=df["project_name"],
    marker=dict(size=10, opacity=0.9, color='#00504a'),
    customdata=df[["community", "record_id"]],
    selected=dict(marker=dict(color='#c63527')),
    hovertemplate="<b>%{text}</b><br>Community: %{customdata[0]}<extra></extra>"
  )
  return map_data


def get_project_card_data_internal(df):
  """Prepare project card data from filtered dataframe."""
  df = add_formatted_list_columns(df, ["project_type", "all_financing_mechanisms"])
  df = format_number_column(df, "total_cost", 0)
  return df.to_dict(orient="records")


# ============= CALLABLE FUNCTION =============
@anvil.server.callable
def get_all_map_and_cards(provinces=None, proj_types=None, stages=None,
                          indigenous_ownership=None, project_scale=None,
                          page=1, page_size=50):
  """
  Single server call that returns BOTH map data and project cards.

  Map: explodes portfolios so each sub-project location gets its own pin.
  Cards: one card per project/portfolio (paginated).
  """

  # --- MAP DATA ---
  map_cols = [
    "record_id", "project_name", "community", "latitude", "longitude",
    "province", "stage", "project_type", "indigenous_ownership",
    "project_scale", "sub_projects",
  ]
  df_map = DATA.loc[:, [c for c in map_cols if c in DATA.columns]].copy()

  # --- CARD DATA ---
  card_cols = [
    "record_id", "project_name", "data_source", "stage", "project_type",
    "province", "total_cost", "project_scale", "all_financing_mechanisms",
    "owners", "indigenous_ownership", "capital_mix",
    "sub_projects", "response_type",
  ]
  df_cards = DATA.loc[:, [c for c in card_cols if c in DATA.columns]].copy()

  # Apply filters
  df_map_filtered = apply_filters(
    df_map, provinces, proj_types, stages,
    indigenous_ownership, project_scale
  )
  df_cards_filtered = apply_filters(
    df_cards, provinces, proj_types, stages,
    indigenous_ownership, project_scale
  )

  # --- MAP: explode portfolios into individual pins ---
  df_map_exploded = explode_for_map(df_map_filtered)
  map_data = get_map_data_internal(df_map_exploded)

  # Build record_id -> map point indices lookup (string keys for serialization)
  record_id_to_map_indices = {}
  if not df_map_exploded.empty:
    for idx, rid in enumerate(df_map_exploded["record_id"]):
      record_id_to_map_indices.setdefault(str(rid), []).append(idx)

  # Flat list: map point index -> record_id (so client can get record_id from point_number)
  map_point_record_ids = (
    [str(rid) for rid in df_map_exploded["record_id"]]
    if not df_map_exploded.empty else []
  )

  # --- CARDS: one per project, paginated ---
  total_count = len(df_cards_filtered)
  start_idx = (page - 1) * page_size
  end_idx = min(start_idx + page_size, total_count)
  df_cards_page = df_cards_filtered.iloc[start_idx:end_idx].copy()

  # Build traces only for this page
  df_cards_page["ownership_traces"] = df_cards_page["owners"].apply(
    lambda x: build_ownership_bar(x, OWNERSHIP_COLORS)
  )
  df_cards_page["capital_mix_traces"] = df_cards_page["capital_mix"].apply(
    lambda x: build_capital_mix_traces(x, CATEGORY_PALETTES)
  )

  results = {
    'map_data': map_data,
    'project_cards': get_project_card_data_internal(df_cards_page),
    'total_count': total_count,
    'page': page,
    'page_size': page_size,
    'has_more': end_idx < total_count,
    'start_idx': start_idx,
    'end_idx': end_idx,
    'record_id_to_map_indices': record_id_to_map_indices,
    'map_point_record_ids': map_point_record_ids,
  }

  return results