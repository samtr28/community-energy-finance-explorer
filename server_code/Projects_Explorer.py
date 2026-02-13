import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import pandas as pd
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
    blend = i * 0.15  # Each step gets 15% lighter
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

# Generate palettes for each category
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

# Color palette for ownership bars (using gradient palette)
OWNERSHIP_COLORS = gradient_palette[::-1]

# ============= DATA LOADING =============
# Load data ONCE at module level - cached in memory
DATA = get_data(project_privacy=True)

# ============= HELPER FUNCTIONS =============
def build_ownership_bar(owners, ownership_colors):
  """Build bar traces for ownership data. Returns list of go.Bar traces."""
  # Normalize to list
  if owners is None:
    return []
  elif isinstance(owners, dict):
    owners = [owners]
  elif not isinstance(owners, (list, tuple)):
    return []

  # Build bar traces
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

    # Cycle through ownership colors
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
  # Normalize to list
  if capital_mix is None:
    return []
  elif isinstance(capital_mix, dict):
    capital_mix = [capital_mix]
  elif not isinstance(capital_mix, (list, tuple)):
    return []

  mix_df = pd.DataFrame(capital_mix)

  if mix_df.empty:
    return []

  # Data cleaning
  mix_df["name"] = mix_df["name"].astype(str).replace({"nan": "Unnamed"})
  mix_df["category"] = mix_df["category"].astype(str).fillna("Unknown")
  mix_df["percent"] = pd.to_numeric(mix_df["percent"], errors='coerce').fillna(0)
  mix_df["amount"] = pd.to_numeric(mix_df["amount"], errors='coerce').fillna(0)
  mix_df["item_type"] = mix_df.get("item_type", "").astype(str)
  mix_df["row"] = ""

  # Calculate total and determine action
  total_percent = mix_df["percent"].sum()
  total_amount = mix_df["amount"].sum()
  difference = 100 - total_percent

  # Handle different scenarios
  if abs(difference) <= 7.5:
    # Small difference: normalize to 100%
    if total_percent > 0:
      mix_df["display_percent"] = (mix_df["percent"] / total_percent) * 100
    else:
      mix_df["display_percent"] = 0
  elif difference > 7.5:
    # Under-accounted: add "Unknown" category to fill the gap
    mix_df["display_percent"] = mix_df["percent"]

    # Calculate the unknown amount based on the proportion
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
  else:  # difference < -7.5 (over-accounted)
    mix_df["display_percent"] = mix_df["percent"]

  # Build traces
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


def apply_filters(df, provinces=None, proj_types=None, stages=None, 
                  indigenous_ownership=None, project_scale=None):
  """
  Apply filters to dataframe. Returns filtered copy.
  Uses list filtering for now - will be updated to set filtering later.
  """
  df = df.copy()

  if provinces:
    df = df[df["province"].isin(provinces)]

  if proj_types:
    df = df[df["project_type"].apply(lambda lst: any(t in lst for t in proj_types))]

  if stages:
    df = df[df["stage"].isin(stages)]

  if indigenous_ownership:
    df = df[df["indigenous_ownership"].isin(indigenous_ownership)]

  if project_scale:
    df = df[df["project_scale"].isin(project_scale)]

  return df


def get_map_data_internal(df):
  """Internal function to create map trace from filtered data."""
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
  """Internal function to prepare project card data from filtered dataframe."""
  # Format columns
  df = add_formatted_list_columns(df, ["project_type", "all_financing_mechanisms"])
  df = format_number_column(df, "total_cost", 0)

  return df.to_dict(orient="records")

def build_ownership_figure(owners, ownership_colors):
  """
  Build a COMPLETE ownership figure ready to render.
  Returns a figure dictionary that client can directly assign.
  """
  # Build the bar traces (reuse existing function)
  bars = build_ownership_bar(owners, ownership_colors)

  if not bars:
    return None

  # Create figure with all traces
  fig = go.Figure(data=bars)

  # Apply ALL layout configuration on server
  fig.update_layout(
    barmode="stack",
    margin=dict(l=5, r=5, t=30, b=5),
    showlegend=False,
    xaxis=dict(ticksuffix="%", visible=False, range=[0, 100]),
    yaxis=dict(visible=False),
    title={
      'text': 'Ownership Distribution',
      'font': {'family': 'Noto Sans', 'size': 16, 'color': 'black'},
      'x': 0.01,
      'xanchor': 'left'
    },
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)'
  )

  # Apply trace-level styling
  fig.update_traces(
    texttemplate="%{customdata[0]}: %{x:.0f}%",
    textposition="inside",
    hovertemplate="<b>%{customdata[0]}</b><br>Type: %{customdata[1]}<br>%: %{x:.1f}<extra></extra>"
  )

  # Return as dictionary (JSON-serializable)
  return fig.to_dict()


def build_capital_mix_figure(capital_mix, category_palettes):
  """
  Build a COMPLETE capital mix figure ready to render.
  Returns a figure dictionary that client can directly assign.
  """
  # Build the bar traces (reuse existing function)
  traces = build_capital_mix_traces(capital_mix, category_palettes)

  if not traces:
    return None

  # Create figure with all traces
  fig = go.Figure(data=traces)

  # Calculate dynamic margin based on number of categories
  num_categories = len(set(tr.name for tr in traces))
  bottom_margin = 0 + (55 * (num_categories // 5))

  # Apply ALL layout configuration on server
  fig.update_layout(
    barmode="stack",
    margin=dict(l=5, r=5, t=35, b=bottom_margin),
    legend=dict(
      orientation="h",
      yanchor="bottom",
      y=-1,
      xanchor="right",
      x=1,
      bgcolor="rgba(0,0,0,0)",
      font=dict(size=10)
    ),
    xaxis=dict(ticksuffix="%", visible=False, range=[0, 100]),
    yaxis=dict(visible=False),
    title={
      'text': 'Capital Mix',
      'font': {'family': 'Noto Sans', 'size': 16, 'color': 'black'},
      'x': 0.01,
      'xanchor': 'left'
    },
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)'
  )

  # Check for warnings and add annotations
  has_unknown = False
  for tr in traces:
    if hasattr(tr, 'name') and tr.name == "Unknown":
      has_unknown = True
      break
    if hasattr(tr, 'customdata') and tr.customdata:
      for cd in tr.customdata:
        if cd and len(cd) > 2 and "Unknown" in str(cd[2]):
          has_unknown = True
          break

  total_percent = sum(tr.x[0] for tr in traces if hasattr(tr, 'x') and tr.x)

  if has_unknown:
    fig.add_annotation(
      text="⚠️ Unknown capital added to reach 100%",
      xref="paper", yref="paper",
      x=0.5, y=1.2,
      showarrow=False,
      font=dict(size=12, color="orange"),
      xanchor="center"
    )
  elif total_percent > 105:
    fig.add_annotation(
      text=f"⚠️ Over-accounted (total: {total_percent:.0f}%)",
      xref="paper", yref="paper",
      x=0.5, y=1.2,
      showarrow=False,
      font=dict(size=12, color="red"),
      xanchor="center"
    )

  # Return as dictionary (JSON-serializable)
  return fig.to_dict()



@anvil.server.callable
def get_all_map_and_cards(provinces=None, proj_types=None, stages=None, 
                          indigenous_ownership=None, project_scale=None,
                          prebuild_limit=15):
  """
  Returns ALL filtered cards, but only builds figures for the first few.
  Rest of the cards will build figures on-demand.
  """
  print("Loading map and card data...")

  # Select columns needed for map
  map_cols = ["record_id", "project_name", "community", "latitude", "longitude", 
              "province", "stage", "project_type", "indigenous_ownership", "project_scale"]
  df_map = DATA.loc[:, map_cols].copy()

  # Select columns needed for cards
  card_cols = ["record_id", "project_name", "data_source", "stage", "project_type", 
               "province", "total_cost", "project_scale", "all_financing_mechanisms", 
               "owners", "indigenous_ownership", "capital_mix"]
  df_cards = DATA.loc[:, card_cols].copy()

  # Apply filters to BOTH dataframes
  df_map_filtered = apply_filters(df_map, provinces, proj_types, stages, 
                                  indigenous_ownership, project_scale)
  df_cards_filtered = apply_filters(df_cards, provinces, proj_types, stages, 
                                    indigenous_ownership, project_scale)

  total_projects = len(df_cards_filtered)
  print(f"Filtered to {total_projects} projects")

  # Split into two groups: prebuild and lazy-build
  df_prebuild = df_cards_filtered.head(prebuild_limit)
  df_lazy = df_cards_filtered.iloc[prebuild_limit:]

  print(f"Pre-building figures for first {len(df_prebuild)} cards...")

  # Build figures for first batch only
  df_prebuild["ownership_figure"] = df_prebuild["owners"].apply(
    lambda x: build_ownership_figure(x, OWNERSHIP_COLORS)
  )
  df_prebuild["capital_mix_figure"] = df_prebuild["capital_mix"].apply(
    lambda x: build_capital_mix_figure(x, CATEGORY_PALETTES)
  )

  # For lazy cards, set figures to None explicitly
  df_lazy["ownership_figure"] = None
  df_lazy["capital_mix_figure"] = None

  # Combine back together
  df_all_cards = pd.concat([df_prebuild, df_lazy], ignore_index=True)

  print("Generating map and card data...")

  results = {
    'map_data': get_map_data_internal(df_map_filtered),
    'project_cards': get_project_card_data_internal(df_all_cards),
    'total_count': total_projects,
    'prebuilt_count': len(df_prebuild)
  }

  print(f"Returning ALL {total_projects} cards ({len(df_prebuild)} with pre-built figures)!")

  return results


@anvil.server.callable
def build_card_figures(record_id, provinces=None, proj_types=None, stages=None,
                       indigenous_ownership=None, project_scale=None):
  """
  Build figures for a single card on-demand.
  Returns dict with ownership_figure and capital_mix_figure.
  """
  print(f"Building figures for card {record_id}...")

  # Get the card data
  card_cols = ["record_id", "owners", "capital_mix"]
  df = DATA.loc[:, card_cols].copy()

  # Apply same filters to ensure we get the right card
  df_filtered = apply_filters(df, provinces, proj_types, stages,
                              indigenous_ownership, project_scale)

  # Find the specific card
  card_data = df_filtered[df_filtered["record_id"] == record_id]

  if card_data.empty:
    print(f"Card {record_id} not found!")
    return None

  # Get the first (should be only) match
  card = card_data.iloc[0]

  # Build both figures
  ownership_fig = build_ownership_figure(card["owners"], OWNERSHIP_COLORS)
  capital_mix_fig = build_capital_mix_figure(card["capital_mix"], CATEGORY_PALETTES)

  print(f"Figures built for card {record_id}")

  return {
    'ownership_figure': ownership_fig,
    'capital_mix_figure': capital_mix_fig
  }