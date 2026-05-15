"""
Cap_Explorer.py — Server module for the Capital Explorer page
=============================================================
Structure:
  1. Imports
  2. Utility functions         — text wrapping, contrast colour, category name normalisation
  3. Data filtering            — apply_filters()
  4. Data processing           — process_capital_mix_data(), get_category_order()
  5. Main callable             — get_all_capital_charts()
  6. Chart creation functions  — one per chart type
  7. Indicators calculation    — calculate_indicators_internal()
  8. Export callable           — export_capital_chart()

Display template is applied centrally in get_all_capital_charts() via
apply_display_template() from Export_Utils. Individual chart functions
only set chart-specific properties.
"""

import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import pandas as pd
import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import plotly.express as px
import textwrap
import math

from .config import (
COLOUR_MAPPING, gradient_palette, dunsparce_colors,
FONT_FAMILY, FONT_SIZE, FONT_COLOR,
)
from .Global_Server_Functions import get_data
from .Export_Utils import export_figure_from_bytes, apply_display_template


# ==================== UTILITY FUNCTIONS ====================

def wrap_text(text, width=15):
  """Wrap long strings with <br> tags for display inside Plotly visualisations."""
  return '<br>'.join(textwrap.wrap(text, width=width))


def get_contrast_color(hex_color):
  """
  Return 'white' or 'black' based on which gives better contrast
  against the given hex background colour (ITU-R BT.601 luminance).
  """
  if not hex_color or not hex_color.startswith('#'):
    return 'white'
  hex_color = hex_color.lstrip('#')
  r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
  return 'black' if (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5 else 'white'


def standardize_category_name(category):
  """
  Normalise raw category strings to the consistent display names used across all charts.
  Handles casing and phrasing variations from the survey data.
  """
  if not category:
    return category
  c = str(category).lower()
  if 'debt'      in c: return 'Debt financing'
  if 'grant'     in c: return 'Grants & non-repayable contributions'
  if 'crowdfund' in c or 'crowd fund' in c: return 'Crowdfunding'
  if 'internal'  in c: return 'Internal capital'
  if 'equity'    in c: return 'External equity investments'
  if 'community' in c: return 'Community financing'
  return category

# Short labels used when collapsing small sources into an "Other" bucket.
# Keeps "Other" labels readable in dense charts (Sankey nodes, treemap tiles, etc.)
CATEGORY_SHORT_LABELS = {
  'External equity investments':          'external equity',
  'Grants & non-repayable contributions': 'grants',
  'Debt financing':                       'debt',
  'Community financing':                  'community finance',
  'Crowdfunding':                         'crowdfunding',
  'Internal capital':                     'internal capital',
}


def group_small_sources(df, by='amount', threshold=None, min_count=None,
                        category_col='category', source_col='source',
                        amount_col='amount', record_col='record_id',
                        force_group=None, omit_categories=None):
  """
  ...
  omit_categories: optional list of category names to skip entirely.
                   Sources in these categories are never grouped — useful for
                   sparse categories (e.g. Crowdfunding) where the user wants
                   to see every source individually.
  """
  if df.empty:
    return df.copy()

  df = df.copy()
  omit_categories = omit_categories or []

  # Work out small_pairs only on the non-omitted slice of the data
  df_for_grouping = df[~df[category_col].isin(omit_categories)]

  if df_for_grouping.empty:
    # Nothing to group, but force_group might still apply below
    small_pairs = set()
  else:
    if by == 'amount':
      if threshold is None:
        raise ValueError("`threshold` is required when by='amount'")
      totals = df_for_grouping.groupby([category_col, source_col])[amount_col].sum()
      small_mask = totals < threshold

    elif by == 'pct_within_category':
      if threshold is None:
        raise ValueError("`threshold` (as a fraction, e.g. 0.03) is required when by='pct_within_category'")
      source_totals = df_for_grouping.groupby([category_col, source_col])[amount_col].sum()
      cat_totals    = df_for_grouping.groupby(category_col)[amount_col].sum()
      pct = source_totals / source_totals.index.get_level_values(category_col).map(cat_totals)
      small_mask = pct < threshold

    elif by == 'count':
      if min_count is None:
        raise ValueError("`min_count` is required when by='count'")
      counts = df_for_grouping.groupby([category_col, source_col])[record_col].nunique()
      small_mask = counts < min_count

    else:
      raise ValueError(f"Unknown grouping mode: {by!r}")

    small_pairs = set(small_mask[small_mask].index.tolist())

  # Force-include certain sources, but still respect omit_categories
  if force_group:
    forced = df[
      df[source_col].isin(force_group) &
      ~df[category_col].isin(omit_categories)
      ][[category_col, source_col]]
    small_pairs.update(map(tuple, forced.drop_duplicates().values.tolist()))

  # Rewrite small sources to "Other {short_category}"
  def relabel(row):
    key = (row[category_col], row[source_col])
    if key in small_pairs:
      short = CATEGORY_SHORT_LABELS.get(row[category_col], row[category_col])
      return f'Other {short}'
    return row[source_col]

  df[source_col] = df.apply(relabel, axis=1)
  return df

# ==================== DATA FILTERING ====================

def apply_filters(df, provinces=None, proj_types=None, stages=None,
                  indigenous_ownership=None, project_scale=None):
  """
  Apply user-selected filters to a dataframe. Returns a filtered copy.
  Silently returns the original dataframe if it is already empty.
  """
  if df.empty:
    return df
  df = df.copy()
  if provinces:            df = df[df['province'].isin(provinces)]
  if proj_types:           df = df[df['project_type'].apply(lambda lst: any(t in lst for t in proj_types))]
  if stages:               df = df[df['stage'].isin(stages)]
  if indigenous_ownership: df = df[df['indigenous_ownership'].isin(indigenous_ownership)]
  if project_scale:        df = df[df['project_scale'].isin(project_scale)]
  return df


# ==================== DATA PROCESSING ====================

def process_capital_mix_data(df):
  """
  Transform the raw survey dataframe into a long-format capital mix dataframe.

  Steps:
    1. Explode capital_mix list into one row per financing item
    2. Explode debt list into one row per debt instrument
    3. Merge debt details (interest rate, repayment period) into capital mix rows
    4. Zero out time columns that do not match the row's category
    5. Convert time-to-funding strings to numeric years
    6. Normalise 'Other' / 'Not sure' source labels
  """
  # Step 1 — Explode capital_mix
  rows = []
  for _, row in df.iterrows():
    for item in (row.get('capital_mix') or []):
      rows.append({
        'record_id':                row.get('record_id'),
        'total_cost':               row.get('total_cost'),
        'name':                     item.get('name'),
        'source':                   item.get('source'),
        'category':                 item.get('category'),
        'item_type':                item.get('item_type'),
        'amount':                   item.get('amount'),
        'project_type':             row.get('project_type'),
        'stage':                    row.get('stage'),
        'province':                 row.get('province'),
        'project_scale':            row.get('project_scale'),
        'grants_time':              row.get('grants_time'),
        'debt_time':                row.get('debt_time'),
        'equity_time':              row.get('equity_time'),
        'community_time':           row.get('community_finance_time'),
        'crowdfunding_time':        row.get('crowdfunding_time'),
        'indigenous_ownership':     row.get('indigenous_ownership'),
        'all_financing_mechanisms': row.get('all_financing_mechanisms'),
      })

  df_long = pd.DataFrame(rows)
  if df_long.empty:
    return pd.DataFrame(columns=[
      'record_id', 'total_cost', 'name', 'source', 'category', 'item_type',
      'amount', 'project_type', 'stage', 'province', 'project_scale',
      'indigenous_ownership', 'all_financing_mechanisms', 'time_to_funding'
    ])

  # Step 2 — Explode debt list
  debt_rows = []
  for _, row in df.iterrows():
    for item in (row.get('debt') or []):
      debt_rows.append({
        'record_id':        row.get('record_id'),
        'total_cost':       row.get('total_cost'),
        'name':             item.get('debt_name'),
        'source':           item.get('debt_source'),
        'debt_interest':    item.get('debt_interest'),
        'repayment_period': item.get('debt_repayment'),
      })

  # Step 3 — Merge debt details
  df_long = pd.merge(
    df_long, pd.DataFrame(debt_rows),
    on=['record_id', 'total_cost', 'name', 'source'], how='left'
  )

  # Step 4 — Zero out mismatched time columns
  time_cols = ['grants_time', 'debt_time', 'equity_time', 'community_time', 'crowdfunding_time']
  time_cats = ['Grants',      'Debt',      'Equity',      'Community finance', 'Crowdfunding']
  for col, cat in zip(time_cols, time_cats):
    df_long.loc[(df_long['category'] != cat) & df_long[col].notnull(), col] = pd.NaT

  # Step 5 — Convert time strings to numeric years
  TIME_MAP = {
    'Less than 1 year': 0.5,
    '2-3 years':        2.5,
    '4-5 years':        4.5,
    '8-10 years':       9.0,
    'More than 10 years': 11.0
  }
  def time_to_numeric(s):
    return np.nan if (pd.isna(s) or s == 'Missing value') else TIME_MAP.get(s, np.nan)

  df_long['time_to_funding'] = df_long.apply(
    lambda row: next((time_to_numeric(row[c]) for c in time_cols if pd.notna(row[c])), np.nan),
    axis=1
  )
  df_long = df_long.drop(columns=time_cols)

  # Step 6 — Normalise ambiguous source labels
  df_long['source'] = df_long['source'].replace({
    'Other':                 'Other/Unknown',
    'Other (please specify)':'Other/Unknown',
    'Not sure':              'Other/Unknown',
    'Aggregate total':       'Other/Unknown',
    'Aggregate Total':       'Other/Unknown',
    "Don't know":            'Other/Unknown',
  })
  mask = df_long['source'] == 'Other/Unknown'
  df_long.loc[mask, 'source'] = df_long.loc[mask, 'source'] + '-' + df_long.loc[mask, 'category']

  # ── TEMPORARY FIX: Reclassify CIB debt for projects 77 & 106 ──
  # TODO: Remove once survey data is recoded
  df_long.loc[
    df_long['record_id'].isin([77, 106]) & (df_long['category'] == 'Debt financing'),
    'source'
    ] = 'Public infrastructure bank/government-sponsored lender'

  df_long['category'] = df_long['category'].apply(standardize_category_name)
  return df_long


def get_category_order(df):
  """
  Return the canonical category display order (ascending by average time-to-funding).
  Internal capital and Other are excluded. Falls back to a hard-coded default if
  the dataframe is empty or missing required columns.
  """
  if df.empty or 'category' not in df.columns or 'time_to_funding' not in df.columns:
    return [
      'Grants & non-repayable contributions', 'Crowdfunding',
      'Community financing', 'External equity investments', 'Debt financing',
    ]
  averages = (
    df[~df['category'].isin(['Internal capital', 'Other'])]
      .groupby('category')['time_to_funding'].mean()
      .sort_values()
  )
  return averages.index.tolist()


# ==================== MAIN CALLABLE ====================

@anvil.server.callable
def get_all_capital_charts(provinces=None, proj_types=None, stages=None,
                           indigenous_ownership=None, project_scale=None):
  """
  Single server call returning all chart figures and indicator values.
  Data is loaded and processed once, shared across all chart builders.
  apply_display_template() is called here on every figure — chart functions
  only need to set chart-specific properties.

  Returns a dict with keys:
    time_chart, sankey, stacked_bar, box_plot, bottleneck_chart,
    treemap, scale_pies, indicators
  """
  # ── Load and process data once ──
  df_raw         = get_data()
  df_capital_mix = process_capital_mix_data(df_raw)

  # ── Three filter variants ──
  df_raw_filtered           = apply_filters(df_raw,         provinces, proj_types, stages, indigenous_ownership, project_scale)
  df_capital_filtered       = apply_filters(df_capital_mix, provinces, proj_types, stages, indigenous_ownership, project_scale)
  df_capital_no_proj_filter = apply_filters(df_capital_mix, provinces, None,       stages, indigenous_ownership, project_scale)
  # ^ Sankey excludes proj_type filter so all project types appear as destination nodes

  # ── Guard: return empty figures if nothing matches ──
  if df_capital_filtered.empty:
    empty_fig = go.Figure()
    empty_fig.update_layout(title=dict(text='No data available for selected filters'))
    return {k: empty_fig for k in [
      'box_plot', 'sankey', 'time_chart', 'stacked_bar',
      'bottleneck_chart', 'treemap', 'scale_pies', 'alt_financing_bar',
    ]}

  # ── Category order — computed once, reused across charts ──
  cat_order     = get_category_order(df_capital_filtered)
  cat_order_rev = list(reversed(cat_order))

    # ── Build all charts and apply the display template to each ──
  sankey_fig = apply_display_template(create_sankey_internal(df_capital_no_proj_filter, proj_types))
  sankey_fig.update_layout(margin=dict(t=80)) 

  return {
    'time_chart':         apply_display_template(create_time_chart_internal(df_capital_filtered,       cat_order)),
    'sankey':             sankey_fig,
    'stacked_bar':        apply_display_template(create_stacked_bar_internal(df_capital_filtered,      cat_order_rev)),
    'box_plot':           apply_display_template(create_box_plot_internal(df_raw_filtered,             cat_order_rev)),
    'bottleneck_chart':   apply_display_template(create_bottleneck_lollipop_internal(df_raw_filtered)),
    'treemap':            apply_display_template(create_treemap_internal(df_raw_filtered)),
    'scale_pies':         apply_display_template(create_scale_pies_internal(df_capital_filtered)),
    'alt_financing_bar': apply_display_template(create_alt_financing_bar_internal(df_raw_filtered)),
  }


# ==================== CHART CREATION ====================
# Each function sets only chart-specific properties.
# Generic styling (backgrounds, fonts, title size, margins) is handled
# by apply_display_template() in get_all_capital_charts() above.
# Title text is still set here since it is chart-specific content.

def create_box_plot_internal(df, category_order):
  """
  Box plot: each financing category's percentage share of total project costs.
  Individual data points overlaid on boxes.
  Chart-specific: x-axis tick angle, y-axis % suffix, axis lines, no legend.
  """
  relevant_columns = [
    'total_percent_grants', 'total_percent_equity', 'total_percent_debts',
    'total_percent_internal', 'total_percent_community_finance', 'total_percent_crowdfund'
  ]
  df_long = df[relevant_columns].melt(var_name='category', value_name='percent')
  df_long = df_long[df_long['percent'] > 0]
  df_long['category'] = (df_long['category']
    .str.replace('total_percent_', '', regex=False)
    .str.replace('_', ' ', regex=False)
    .apply(standardize_category_name))

  filtered_order = [c for c in category_order if c in df_long['category'].values]
  color_map = {c: COLOUR_MAPPING.get(c, '#808080') for c in df_long['category'].unique()}

  fig = px.box(
    df_long, x='category', y='percent', points='all', color='category',
    color_discrete_map=color_map,
    category_orders={'category': filtered_order}
  )
  fig.update_layout(
    showlegend=False,
    yaxis_title='', xaxis_title='',
    xaxis=dict(tickangle=20, linecolor='grey', showline=True),
    yaxis=dict(ticksuffix='%', linecolor='grey', showline=True),
    margin=dict(l=0, r=0, b=0),
    title=dict(text='Typical Share of Project Costs by Capital Source'),
  )
  return fig


def create_time_chart_internal(df, category_order):
  """
  Horizontal bar chart: average time-to-funding per financing category.
  Internal capital excluded. Bar labels include category name and value.
  Chart-specific: hidden axes, bar colours, auto-contrasted text colours.
  """
  df          = df[df['category'] != 'Internal capital']
  averages    = df.groupby('category')['time_to_funding'].mean().reindex(category_order)
  bar_colors  = [COLOUR_MAPPING.get(c, '#808080') for c in averages.index]
  text_colors = [get_contrast_color(c) for c in bar_colors]

  fig = go.Figure(data=[go.Bar(
    y=averages.index, x=averages.values, orientation='h',
    text=[f'{c}: {v:.1f} years' for c, v in zip(averages.index, averages.values)],
    textposition='inside',
    textfont=dict(family=FONT_FAMILY, size=FONT_SIZE, color=text_colors),
    marker=dict(color=bar_colors)
  )])
  fig.update_layout(
    yaxis_title='', xaxis_title='', showlegend=False,
    xaxis=dict(visible=False),
    yaxis=dict(showticklabels=False),
    margin=dict(l=0, r=0, b=0),
    title=dict(text='Average Time to Secure Funding'),
  )
  return fig


def create_sankey_internal(df, proj_types=None):
  """
  Sankey: capital flow from Funding Source → Category → Project Type.
  Internal capital handled separately (no upstream source nodes).
  Links are semi-transparent versions of the category colour.
  Chart-specific: node/link colours, bold node labels.
  Note: proj_type filter excluded from input df — all project types appear.
  """
  df = df.copy()
  for col in ['project_type', 'amount', 'category', 'source']:
    if col not in df.columns:
      df[col] = None

  df['project_type'] = df['project_type'].apply(
    lambda x: x if isinstance(x, list) else ([] if pd.isna(x) else [x])
  )
  df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
  
  # ── Group small sources to reduce Sankey node clutter ──
  df = group_small_sources(df, by='pct_within_category', threshold=0.03)
  
  # Split amount evenly across project types
  df['pt_count'] = df['project_type'].apply(len).replace(0, 1)
  # Split amount evenly across project types
  df['pt_count'] = df['project_type'].apply(len).replace(0, 1)
  df['amount']   = df['amount'] / df['pt_count']
  df = df.explode('project_type').reset_index(drop=True)

  if proj_types:
    df = df[df['project_type'].isin(proj_types)]
  df = df.drop(columns=['pt_count'], errors='ignore')

  df_internal = df[df['category'] == 'Internal capital'].copy()
  df_other    = df[df['category'] != 'Internal capital'].copy()

  sources_list    = list(df_other['source'].dropna().unique())
  categories_list = list(df_other['category'].dropna().unique())
  proj_list       = list(df['project_type'].dropna().unique())

  all_nodes = []
  for lst in (sources_list, categories_list, ['Internal capital'], proj_list):
    for item in lst:
      if item not in all_nodes:
        all_nodes.append(item)
  node_index = {label: i for i, label in enumerate(all_nodes)}

  agg_s2c = df_other.groupby(['source',   'category'],     dropna=False)['amount'].sum().reset_index()
  agg_c2p = df_other.groupby(['category', 'project_type'], dropna=False)['amount'].sum().reset_index()
  agg_i2p = df_internal.groupby(['project_type'],          dropna=False)['amount'].sum().reset_index()

  sources = ([node_index.get(r['source'])   for _, r in agg_s2c.iterrows()] +
             [node_index.get(r['category']) for _, r in agg_c2p.iterrows()] +
             [node_index.get('Internal capital')] * len(agg_i2p))
  targets = ([node_index.get(r['category'])    for _, r in agg_s2c.iterrows()] +
             [node_index.get(r['project_type'])for _, r in agg_c2p.iterrows()] +
             [node_index.get(r['project_type'])for _, r in agg_i2p.iterrows()])
  values  = list(agg_s2c['amount']) + list(agg_c2p['amount']) + list(agg_i2p['amount'])

  def make_transparent(color):
    try:
      if isinstance(color, str) and color.startswith('#') and len(color) == 7:
        r, g, b = int(color[1:3],16), int(color[3:5],16), int(color[5:7],16)
        return f'rgba({r},{g},{b},0.3)'
    except Exception:
      pass
    return 'rgba(128,128,128,0.3)'

  link_colors = (
    [make_transparent(COLOUR_MAPPING.get(r['category'], '#808080')) for _, r in agg_s2c.iterrows()] +
    [make_transparent(COLOUR_MAPPING.get(r['category'], '#808080')) for _, r in agg_c2p.iterrows()] +
    [make_transparent(COLOUR_MAPPING.get('Internal capital', '#808080'))] * len(agg_i2p)
  )

  # Tiny invisible link keeps Internal capital in the middle column
  internal_idx = node_index.get('Internal capital')
  if sources_list and internal_idx is not None:
    sources     = list(sources)     + [node_index.get(sources_list[0])]
    targets     = list(targets)     + [internal_idx]
    values      = list(values)      + [0.001]
    link_colors = list(link_colors) + ['rgba(0,0,0,0)']

  valid = [(s, t, v, c) for s, t, v, c in zip(sources, targets, values, link_colors)
           if s is not None and t is not None and v and v > 0]
  if not valid:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No data for selected filters'))
    return fig

  sv, tv, vv, cv = zip(*valid)
  source_to_cat  = (df_other.groupby('source')['category'].first().to_dict()
                    if not df_other.empty else {})
  node_colors = [
    COLOUR_MAPPING.get(source_to_cat.get(n), '#808080') if n in sources_list else
    COLOUR_MAPPING.get(n, '#808080')                    if n in categories_list or n == 'Internal capital' else
    '#696969'
    for n in all_nodes
  ]

  fig = go.Figure(data=[go.Sankey(
    arrangement='perpendicular',
    node=dict(
      align='center', thickness=15, line=dict(color='white', width=0),
      label=[str(n) for n in all_nodes], color=node_colors,
      hovertemplate='%{label}<br>$%{value:,.0f}<extra></extra>'
    ),
    link=dict(
      source=list(sv), target=list(tv), value=list(vv), color=list(cv),
      hovertemplate='%{source.label} → %{target.label}<br>$%{value:,.0f}<extra></extra>'
    ),
    # Bold node labels — intentional override of base font weight
    textfont=dict(color=FONT_COLOR, family=FONT_FAMILY, size=FONT_SIZE, weight='bold')
  )])
  fig.update_layout(
    margin=dict(l=0, r=0, b=10, t=0),  # increase t to make room for headers
    title=dict(
      text='The Landscape of Community Energy Finance in Canada',
      x=0,        # 0=left, 0.5=center, 1=right
      y=1,     # 0=bottom, 1=top — adjust this to move up/down
      xanchor='left',
      yanchor='top',
    ),
    annotations=[
      dict(
        text='<u>SOURCES & INTERMEDIARIES</u>',
        x=0, y=1.02,
        xref='paper', yref='paper',
        xanchor='left', yanchor='bottom',
        showarrow=False,
        font=dict(family=FONT_FAMILY, size=13, color='#888888', weight='bold'),
      ),
      dict(
        text='<u>INSTRUMENTS/MECHANISMS</u>',
        x=0.5, y=1.02,
        xref='paper', yref='paper',
        xanchor='center', yanchor='bottom',
        showarrow=False,
        font=dict(family=FONT_FAMILY, size=13, color='#888888', weight='bold'),
      ),
      dict(
        text='<u>ENERGY TECHNOLOGIES</u>',
        x=1, y=1.02,
        xref='paper', yref='paper',
        xanchor='right', yanchor='bottom',
        showarrow=False,
        font=dict(family=FONT_FAMILY, size=13, color='#888888', weight='bold'),
      ),
    ],
  )
  return fig


def create_stacked_bar_internal(df, category_order):
  """
  Horizontal stacked bar: funding source breakdown within each category.
  Excludes Internal capital and Other.
  Shades generated per category; labels shown for segments >=5%.
  Chart-specific: barmode stack, hidden x-axis, y-axis category order, bar text colours.
  """
  df = df[~df['category'].isin(['Internal capital', 'Other'])]

  # ── Collapse sources contributing < 3% of category total ──
  df = group_small_sources(df, by='pct_within_category', threshold=0.05)

  df_grouped = df.groupby(['category', 'source'])['amount'].sum().reset_index()
  group_totals = df_grouped.groupby('category')['amount'].sum().rename('group_total')
  df_grouped = df_grouped.join(group_totals, on='category')
  df_grouped['percentage'] = df_grouped['amount'] / df_grouped['group_total'] * 100

  group_order = [c for c in category_order if c in df_grouped['category'].values]

  def generate_shades(hex_color, n):
    if not hex_color or not hex_color.startswith('#'):
      hex_color = '#808080'
    r, g, b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
    return [f'#{min(255,int(r*(0.75+0.6*i/max(n-1,1)))):02x}'
            f'{min(255,int(g*(0.75+0.6*i/max(n-1,1)))):02x}'
            f'{min(255,int(b*(0.75+0.6*i/max(n-1,1)))):02x}' for i in range(n)]

  color_map, order_map = {}, {}
  for grp in group_order:
    srcs   = df_grouped[df_grouped['category'] == grp].sort_values('amount', ascending=False)['source'].tolist()
    shades = generate_shades(COLOUR_MAPPING.get(grp, '#808080'), len(srcs))
    for i, src in enumerate(srcs):
      color_map[(grp, src)] = shades[i]
      order_map[(grp, src)] = i

  df_grouped['src_order'] = df_grouped.apply(
    lambda r: order_map.get((r['category'], r['source']), 999), axis=1
  )
  all_sources = []
  for grp in group_order:
    for src in df_grouped[df_grouped['category'] == grp].sort_values('src_order')['source']:
      if src not in all_sources:
        all_sources.append(src)

  traces = []
  for src in all_sources:
    for _, row in df_grouped[df_grouped['source'] == src].iterrows():
      color = color_map.get((row['category'], src), '#808080')
      label = f'{src}: {row["percentage"]:.1f}%' if row['percentage'] >= 5 else ''
      traces.append(go.Bar(
        name=src,
        y=[row['category']], x=[row['percentage']], orientation='h',
        text=[label], textposition='inside',
        textfont=dict(size=FONT_SIZE, color=get_contrast_color(color), family=FONT_FAMILY),
        marker=dict(color=color),
        hovertemplate='%{fullData.name}<br>%{x:.1f}%<extra></extra>',
        showlegend=False
      ))

  fig = go.Figure(data=traces)
  fig.update_layout(
    barmode='stack', showlegend=False,
    xaxis=dict(visible=False),
    yaxis=dict(categoryorder='array', categoryarray=list(reversed(group_order))),
    margin=dict(l=0, r=0, b=0),
    title=dict(text='Sources of Capital Within Each Financing Category'),
  )
  return fig


def create_bottleneck_lollipop_internal(df):
  """
  Lollipop chart: count of projects citing each key financing bottleneck.
  Four pre-selected bottlenecks shown.
  Chart-specific: hidden axes, lollipop colours, annotation styles.
  Annotation fonts are set explicitly so apply_display_template skips them:
    - count dots: white size 16 (readable on coloured dot)
    - category labels: dark teal size 14
  """
  BOTTLENECKS_TO_SHOW = [
    'Difficulty securing up-front capital',
    'Limited access to grants or subsidies',
    'High financing costs',
    'Limited investor interest in community-led projects',
  ]

  counts_df = (df['bottlenecks'].explode().value_counts()
    .reset_index()
    .rename(columns={'index': 'bottleneck', 'bottlenecks': 'count'}))
  counts_df.columns = ['bottleneck', 'count']
  counts_df = (counts_df[counts_df['bottleneck'].isin(BOTTLENECKS_TO_SHOW)]
    .sort_values('count', ascending=True))

  # ── Guard: no bottleneck data for current filters ──
  if counts_df.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No data available for selected filters'))
    return fig

  bottlenecks = counts_df['bottleneck'].tolist()
  counts      = counts_df['count'].tolist()
  y_pos       = list(range(len(bottlenecks)))
  color       = dunsparce_colors[1]

  fig = make_subplots()

  for i, (label, count) in enumerate(zip(bottlenecks, counts)):
    fig.add_scatter(
      x=[0, count], y=[i, i], mode='lines',
      line=dict(color=color, width=6), showlegend=False, hoverinfo='skip'
    )
    # Explicit font — preserves dark teal colour through apply_display_template
    fig.add_annotation(
      text=label, x=0.1, y=i + 0.37, xanchor='left', yanchor='middle', showarrow=False,
      font=dict(family=FONT_FAMILY, size=14, color=dunsparce_colors[5])
    )
    # Explicit font — preserves white colour + larger size through apply_display_template
    fig.add_annotation(
      text=f'<b>{count}</b>', x=count, y=i, xanchor='center', yanchor='middle', showarrow=False,
      font=dict(family=FONT_FAMILY, size=16, color='white')
    )

  fig.add_scatter(
    x=counts, y=y_pos, mode='markers',
    marker=dict(size=30, color=color), showlegend=False,
    hovertemplate='<b>%{text}</b><br>Count: %{x}<extra></extra>',
    text=bottlenecks
  )
  fig.update_xaxes(visible=False, range=[0, max(counts) * 1.15] if counts else [0, 10], showgrid=False)
  fig.update_yaxes(visible=False, showgrid=False)
  fig.update_layout(
    margin=dict(l=0, r=0, b=0),
    title=dict(text='Financing Bottlenecks'),
  )
  return fig


def create_treemap_internal(df):
  """
  Treemap with toggle between project count (from financing_mech, filtered to
  direct sources of capital) and dollar amount (from capital_mix).
  Tile size = count or $ depending on selected mode.
  Chart-specific: per-tile text colours auto-contrasted; toggle buttons added
  to switch between the two metrics.
  """
  if df.empty or 'financing_mech' not in df.columns or 'capital_mix' not in df.columns:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No data available for selected filters'))
    return fig

  # ── Count data: from financing_mech, filtered to direct sources only ──
  count_rows = []
  for _, row in df.iterrows():
    for item in (row.get('financing_mech') or []):
      if item.get('parent') != 'Direct sources of capital':
        continue
      count_rows.append({
        'record_id': row.get('record_id'),
        'source':    item.get('source'),
        'category':  standardize_category_name(item.get('category')),
      })

  # ── Amount data: from capital_mix ──
  amount_rows = []
  for _, row in df.iterrows():
    for item in (row.get('capital_mix') or []):
      amount_rows.append({
        'record_id': row.get('record_id'),
        'source':    item.get('source'),
        'category':  standardize_category_name(item.get('category')),
        'amount':    pd.to_numeric(item.get('amount'), errors='coerce') or 0,
      })

  df_count_long  = pd.DataFrame(count_rows)
  df_amount_long = pd.DataFrame(amount_rows)


  if df_count_long.empty and df_amount_long.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No financing data available'))
    return fig

  # ── Group small sources independently for each mode ──
  df_count_long = group_small_sources(
    df_count_long,
    by='count',
    min_count=2,
    force_group=['Other', 'Not sure', 'Aggregate total', 'Aggregate Total',
                 "Don't know", 'N/A'],
    omit_categories=['Internal Capital'],
  )

  df_amount_long = group_small_sources(
    df_amount_long,
    by='pct_within_category',
    threshold=0.1,
    force_group=['Other', 'Not sure', 'Aggregate total', 'Aggregate Total',
                 "Don't know", 'N/A'],
    omit_categories=['Crowdfunding'],
  )

  # ── Aggregate to (source, category, value) shape ──
  df_count  = df_count_long.groupby(['source', 'category']).size().reset_index(name='value')
  df_amount = df_amount_long.groupby(['source', 'category'])['amount'].sum().reset_index(name='value')

  # ── Helper to build one treemap trace ──
  def build_trace(grouped_df, visible, hover_prefix=''):
    if grouped_df.empty:
      return go.Treemap(labels=[], parents=[], values=[], visible=visible)

    cat_totals = grouped_df.groupby('category')['value'].sum().to_dict()
    labels, parents, values, colors, text_colors = [], [], [], [], []

    for cat in grouped_df['category'].unique():
      labels.append(cat)
      parents.append('')
      values.append(cat_totals[cat])
      col = COLOUR_MAPPING.get(cat, '#808080')
      colors.append(col)
      text_colors.append(get_contrast_color(col))

    for _, r in grouped_df.iterrows():
      labels.append(wrap_text(r['source'], width=20) if r['source'] else r['source'])
      parents.append(r['category'])
      values.append(r['value'])
      col = COLOUR_MAPPING.get(r['category'], '#808080')
      colors.append(col)
      text_colors.append(get_contrast_color(col))

    return go.Treemap(
      labels=labels, parents=parents, values=values,
      branchvalues='total',
      visible=visible,
      marker=dict(colors=colors, line=dict(color='white', width=2)),
      textfont=dict(family=FONT_FAMILY, size=FONT_SIZE, color=text_colors),
      textposition='middle center',
      hovertemplate='<b>%{label}</b><br>' + hover_prefix + '%{value:,.0f}<extra></extra>',
    )

  # ── Build figure with both traces, count visible by default ──
  fig = go.Figure()
  fig.add_trace(build_trace(df_count,  visible=True,  hover_prefix=''))
  fig.add_trace(build_trace(df_amount, visible=False, hover_prefix='$'))

  fig.update_layout(
    margin=dict(l=0, r=0, b=0),
    title=dict(text='Common Financing Mechanisms in the Dataset'),
    updatemenus=[dict(
      type='buttons',
      direction='left',
      buttons=[
        dict(
          label='By Project Count',
          method='update',
          args=[{'visible': [True, False]}],
        ),
        dict(
          label='By Dollar Amount',
          method='update',
          args=[{'visible': [False, True]}],
        ),
      ],
      pad={'r': 10, 't': 10},
      showactive=True,
      x=0.5, y=1.07,
      xanchor='left', yanchor='top',
      bgcolor='rgba(255, 255, 255, 0.8)',
      bordercolor='gray',
      borderwidth=1,
    )],
  )

  return fig


def create_scale_pies_internal(df):
  SCALE_ORDER = [
    'Micro (< $100K)', 'Small ($100K-$1M)', 'Medium ($1M-$5M)',
    'Large ($5M-$25M)', 'Very Large ($25M-$100M)', 'Mega (> $100M)'
  ]
  scales = [s for s in SCALE_ORDER if s in df['project_scale'].values]
  if not scales:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No data available'))
    return fig

  all_cats = sorted(df['category'].unique())

  fig = go.Figure()
  n_pies = len(scales)

  for i, scale in enumerate(scales):
    sub = df[df['project_scale'] == scale]
    n   = sub['record_id'].nunique()

    # ── View A: Total Funding (dollar-weighted — sum of amount) ──
    total_by_cat = sub.groupby('category', as_index=False)['amount'].sum()
    total_by_cat = total_by_cat.sort_values('category').reset_index(drop=True)

    # ── View B: Typical Project (project-weighted — mean of project-level %s) ──
    proj_cat   = sub.groupby(['record_id', 'category'])['amount'].sum().reset_index()
    proj_total = sub.groupby('record_id')['amount'].sum()
    proj_cat['pct'] = proj_cat.apply(
      lambda r: (r['amount'] / proj_total[r['record_id']] * 100)
      if proj_total[r['record_id']] > 0 else 0,
      axis=1,
    )
    avg_pct = (
      proj_cat.pivot_table(index='record_id', columns='category', values='pct', fill_value=0)
        .mean()
        .reset_index()
    )
    avg_pct.columns = ['category', 'avg_pct']
    avg_pct = avg_pct.sort_values('category').reset_index(drop=True)

    pad     = 0.01
    x_start = i / n_pies + pad
    x_end   = (i + 1) / n_pies - pad
    domain  = dict(x=[x_start, x_end], y=[0.0, 1.0])

    title_style = dict(
      text=f'{scale}<br>({n} projects)',
      position='top center',
      font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),
    )

    # Trace A — Total Funding (visible)
    fig.add_trace(go.Pie(
      labels=total_by_cat['category'],
      values=total_by_cat['amount'],
      domain=domain, title=title_style,
      marker=dict(colors=[COLOUR_MAPPING.get(c, '#808080') for c in total_by_cat['category']]),
      texttemplate='%{percent:.1%}', textposition='inside',
      textfont=dict(family=FONT_FAMILY, size=FONT_SIZE, color='white'),
      sort=False,
      hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<br>%{percent} of total<extra></extra>',
      showlegend=False, visible=True,
    ))

    # Trace B — Typical Project (hidden)
    fig.add_trace(go.Pie(
      labels=avg_pct['category'],
      values=avg_pct['avg_pct'],
      domain=domain, title=title_style,
      marker=dict(colors=[COLOUR_MAPPING.get(c, '#808080') for c in avg_pct['category']]),
      texttemplate='%{percent:.1%}', textposition='inside',
      textfont=dict(family=FONT_FAMILY, size=FONT_SIZE, color='white'),
      sort=False,
      hovertemplate='<b>%{label}</b><br>%{value:.1f}% avg per project<extra></extra>',
      showlegend=False, visible=False,
    ))

  # ── Dummy scatter traces to populate the standard plotly legend ──
  # Pie traces have showlegend=False to avoid duplicates across scales.
  # These invisible traces carry the legend entries instead.
  for cat in all_cats:
    fig.add_trace(go.Scatter(
      x=[None], y=[None],
      mode='markers',
      marker=dict(size=10, color=COLOUR_MAPPING.get(cat, '#808080'), symbol='square'),
      name=cat,
      showlegend=True,
      hoverinfo='skip',
    ))

  # ── Visibility: pie traces toggle; legend traces stay visible always ──
  n_legend      = len(all_cats)
  vis_total     = [True,  False] * n_pies + [True] * n_legend
  vis_avg       = [False, True]  * n_pies + [True] * n_legend

  fig.update_layout(
    title=dict(text='Funding distribution by project scale'),
    showlegend=True,
    legend=dict(orientation='h', y=-0.15, x=0.5, xanchor='center'),
    xaxis=dict(visible=False),
    yaxis=dict(visible=False),
    updatemenus=[dict(
      type='buttons', direction='left',
      buttons=[
        dict(label='Total Funding',   method='update', args=[{'visible': vis_total}]),
        dict(label='Typical Project', method='update', args=[{'visible': vis_avg}]),
      ],
      pad={'r': 10, 't': 10}, showactive=True,
      x=0.5, y=1.12, xanchor='left', yanchor='top',
      bgcolor='rgba(255,255,255,0.8)', bordercolor='gray', borderwidth=1,
    )],
    margin=dict(l=0, r=0, b=80, t=40),
  )
  return fig


def create_alt_financing_bar_internal(df):
  """
  Horizontal stacked bar chart: project count per grouped financing category,
  stacked by individual source/mechanism within each group.
  Each data `category` is mapped to one of four display groups (so all
  sources — including 'Other' and 'Don't know' — are included). Group base
  colours come from COLOUR_MAPPING; subsegments within a group are shades of
  that base colour. Source labels appear directly below each segment.
  """
  # Map each data category → display group (no more keyword matching on source)
  CATEGORY_TO_GROUP = {
    'Feed-in tariffs/power purchase agreements': 'Revenue support mechanisms',
    'Loan guarantees/credit enhancements':       'Risk reduction & credit enhancement',
    'Tax credits/accelerated depreciation':      'Tax & cost reduction incentives',
    'Leasing/third-party ownership models':      'Delivery & ownership structures',
    'Public Private Partnership (P3)':           'Delivery & ownership structures',
  }

  GROUP_TO_COLOUR_KEY = {
    'Revenue support mechanisms':          'Feed-in tariffs/power purchase agreements',
    'Risk reduction & credit enhancement': 'Loan guarantees/credit enhancements',
    'Tax & cost reduction incentives':     'Tax credits/accelerated depreciation',
    'Delivery & ownership structures':     'Leasing/third-party ownership models',
  }

  GROUP_ORDER = [
    'Revenue support mechanisms',
    'Risk reduction & credit enhancement',
    'Tax & cost reduction incentives',
    'Delivery & ownership structures',
  ]

  if df.empty or 'financing_mech' not in df.columns:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No financing mechanism data available'))
    return fig

  flat = pd.json_normalize(df['financing_mech'].explode().dropna())
  if flat.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No financing mechanism data available'))
    return fig

  parents_of_interest = [
    'Alternative financing structures and partnership models',
    'Financial support instruments',
  ]
  sub = flat[flat['parent'].isin(parents_of_interest)].copy()
  if sub.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No data for selected filters'))
    return fig

  # ── Map each row to a group based on its category ──
  sub['group'] = sub['category'].map(CATEGORY_TO_GROUP)
  sub = sub[sub['group'].notna()]

  # ── Drop "Don't know" sources ──
  sub = sub[~sub['source'].astype(str).str.strip().str.lower().eq("don't know")]

  if sub.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No data for selected filters'))
    return fig

  # Keep category in the aggregation so segments from different categories
  # within the same group stay distinct (e.g. P3's "Other" vs Leasing's "Other")
  df_grouped = sub.groupby(['group', 'category', 'source'], as_index=False)['count'].sum()

  # ── Shades start at base colour and lighten toward white; single segment keeps base ──
  def generate_shades(base_color, n):
    if not base_color or not base_color.startswith('#'):
      base_color = '#808080'
    if n == 1:
      return [base_color]
    r, g, b = int(base_color[1:3],16), int(base_color[3:5],16), int(base_color[5:7],16)
    shades = []
    for i in range(n):
      # i=0 → base colour, i=n-1 → lightened by ~55% toward white
      amount = 0.55 * i / (n - 1)
      nr = int(r + (255 - r) * amount)
      ng = int(g + (255 - g) * amount)
      nb = int(b + (255 - b) * amount)
      shades.append(f'#{nr:02x}{ng:02x}{nb:02x}')
    return shades

  groups_with_data = [g for g in GROUP_ORDER if g in df_grouped['group'].values]

  traces = []
  annotations = []

  for grp in groups_with_data:
    grp_data = df_grouped[df_grouped['group'] == grp].sort_values('count', ascending=False)

    colour_key = GROUP_TO_COLOUR_KEY.get(grp, grp)
    base       = COLOUR_MAPPING.get(colour_key, '#808080')
    shades     = generate_shades(base, len(grp_data))

    cumulative = 0
    for i, (_, row) in enumerate(grp_data.iterrows()):
      color    = shades[i]
      x_middle = cumulative + row['count'] / 2
      cumulative += row['count']

      # Include category in hover so 'Other' (which can appear in multiple categories) is disambiguated
      hover = (f"<b>{row['source']}</b>"
               f"<br>Category: {row['category']}"
               f"<br>Count: %{{x}}<extra></extra>")

      traces.append(go.Bar(
        name=row['source'],
        y=[grp],
        x=[row['count']],
        orientation='h',
        marker=dict(color=color),
        hovertemplate=hover,
        showlegend=False,
      ))

      # Source label directly below the segment
      annotations.append(dict(
        x=x_middle, y=grp,
        yshift=-22,
        text=wrap_text(row['source'], width=20),
        showarrow=False,
        xanchor='center', yanchor='top',
        font=dict(family=FONT_FAMILY, size=10, color=FONT_COLOR),
      ))

  fig = go.Figure(data=traces)
  fig.update_layout(
    barmode='stack',
    bargap=0.45,
    showlegend=False,
    annotations=annotations,
    xaxis=dict(title='Number of projects', linecolor='grey', showline=True, tickformat='d'),
    yaxis=dict(categoryorder='array', categoryarray=list(reversed(groups_with_data))),
    margin=dict(l=0, r=0, b=40, t=40),
    title=dict(text='Alternative structures and support mechanisms reported by projects'),
  )
  return fig
# ==================== EXPORT CALLABLE ====================

@anvil.server.callable
def export_capital_chart(chart_key, img_b64, active_filters, chart_title=''):
  return export_figure_from_bytes(
    img_b64,
    active_filters,
    filename=f'{chart_key}_export.png',
    chart_title=chart_title,
  )