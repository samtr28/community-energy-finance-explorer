"""
Cap_Explorer.py — Server module for the Capital Explorer page
=============================================================
Handles all data processing and chart generation for the capital explorer page.

Structure:
  - Imports & configuration
  - Utility functions         (text, colour, category helpers)
  - Data processing           (process_capital_mix_data, apply_filters, get_category_order)
  - Main callable             (get_all_capital_charts)
  - Chart creation functions  (one per chart type)
  - Indicators calculation    (calculate_indicators_internal)
  - Export callable           (export_capital_chart)
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

from .config import COLOUR_MAPPING, gradient_palette, dunsparce_colors
from .Global_Server_Functions import get_data
from .Export_Utils import export_figure_from_bytes


# ==================== UTILITY FUNCTIONS ====================

def wrap_text(text, width=15):
  """Wrap long text with <br> tags for display inside Plotly visualisations."""
  return '<br>'.join(textwrap.wrap(text, width=width))


def get_contrast_color(hex_color):
  """
  Returns 'white' or 'black' depending on which gives better contrast
  against the given hex background colour.
  Uses the standard luminance formula (ITU-R BT.601).
  """
  if not hex_color or not hex_color.startswith('#'):
    return 'white'
  hex_color = hex_color.lstrip('#')
  r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
  luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
  return 'black' if luminance > 0.5 else 'white'


def standardize_category_name(category):
  """
  Normalise category strings to consistent display names used across all charts.
  Handles variations in casing and phrasing from the raw data.
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


# ==================== DATA FILTERING ====================

def apply_filters(df, provinces=None, proj_types=None, stages=None,
                  indigenous_ownership=None, project_scale=None):
  """
  Apply user-selected filters to a dataframe. Returns a filtered copy.
  Silently returns the original if the dataframe is already empty.
  """
  if df.empty:
    return df

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


# ==================== DATA PROCESSING ====================

def process_capital_mix_data(df):
  """
  Transform the raw survey dataframe into a long-format capital mix dataframe.

  Steps:
    1. Explode capital_mix list column into one row per financing item
    2. Explode debt list column into one row per debt instrument
    3. Merge debt details (interest, repayment) into capital mix rows
    4. Zero out time columns that don't match the row's category
    5. Convert time-to-funding strings to numeric years
    6. Normalise 'Other'/'Not sure' source labels
  """
  # Step 1 — Explode capital_mix
  rows = []
  for _, row in df.iterrows():
    for item in (row.get('capital_mix') or []):
      rows.append({
        'record_id':               row.get('record_id'),
        'total_cost':              row.get('total_cost'),
        'name':                    item.get('name'),
        'source':                  item.get('source'),
        'category':                item.get('category'),
        'item_type':               item.get('item_type'),
        'amount':                  item.get('amount'),
        'project_type':            row.get('project_type'),
        'stage':                   row.get('stage'),
        'province':                row.get('province'),
        'project_scale':           row.get('project_scale'),
        'grants_time':             row.get('grants_time'),
        'debt_time':               row.get('debt_time'),
        'equity_time':             row.get('equity_time'),
        'community_time':          row.get('community_finance_time'),
        'crowdfunding_time':       row.get('crowdfunding_time'),
        'indigenous_ownership':    row.get('indigenous_ownership'),
        'all_financing_mechanisms':row.get('all_financing_mechanisms'),
      })

  df_long = pd.DataFrame(rows)

  if df_long.empty:
    return pd.DataFrame(columns=[
      'record_id', 'total_cost', 'name', 'source', 'category',
      'item_type', 'amount', 'project_type', 'stage', 'province',
      'project_scale', 'indigenous_ownership', 'all_financing_mechanisms',
      'time_to_funding'
    ])

  # Step 2 — Explode debt list
  debt_rows = []
  for _, row in df.iterrows():
    for item in (row.get('debt') or []):
      debt_rows.append({
        'record_id':       row.get('record_id'),
        'total_cost':      row.get('total_cost'),
        'name':            item.get('debt_name'),
        'source':          item.get('debt_source'),
        'debt_interest':   item.get('debt_interest'),
        'repayment_period':item.get('debt_repayment'),
      })
  df_debt = pd.DataFrame(debt_rows)

  # Step 3 — Merge debt details into capital mix
  df_long = pd.merge(
    df_long, df_debt,
    on=['record_id', 'total_cost', 'name', 'source'],
    how='left'
  )

  # Step 4 — Zero out time columns that don't match the row's category
  time_columns = ['grants_time', 'debt_time', 'equity_time', 'community_time', 'crowdfunding_time']
  category_map = ['Grants', 'Debt', 'Equity', 'Community finance', 'Crowdfund']
  for col, cat in zip(time_columns, category_map):
    df_long.loc[(df_long['category'] != cat) & df_long[col].notnull(), col] = pd.NaT

  # Step 5 — Convert time strings to numeric years
  def time_to_numeric(time_str):
    mapping = {
      'Less than 1 year': 0.5,
      '2-3 years':        2.5,
      '4-5 years':        4.5,
      '8-10 years':       9.0,
    }
    if pd.isna(time_str) or time_str == 'Missing value':
      return np.nan
    return mapping.get(time_str, np.nan)

  df_long['time_to_funding'] = df_long.apply(
    lambda row: next(
      (time_to_numeric(row[col]) for col in time_columns if pd.notna(row[col])),
      np.nan
    ),
    axis=1
  )
  df_long = df_long.drop(columns=time_columns)

  # Step 6 — Normalise ambiguous source labels
  df_long['source'] = df_long['source'].replace({
    'Other':                'Other/Unknown',
    'Other (please specify)':'Other/Unknown',
    'Not sure':             'Other/Unknown',
    'Aggregate total':      'Other/Unknown',
    'Aggregate Total':      'Other/Unknown',
    "Don't know":           'Other/Unknown',
  })
  mask = df_long['source'] == 'Other/Unknown'
  df_long.loc[mask, 'source'] = df_long.loc[mask, 'source'] + '-' + df_long.loc[mask, 'category']

  # ── TEMPORARY FIX: Reclassify CIB debt for projects 77 & 106 ──
  # CIB = Canada Infrastructure Bank, should be "Public infrastructure bank..."
  # TODO: Remove once survey data is recoded
  df_long.loc[
    df_long['record_id'].isin([77, 106]) & (df_long['category'] == 'Debt financing'),
    'source'
    ] = 'Public infrastructure bank/government-sponsored lender'

  df_long['category'] = df_long['category'].apply(standardize_category_name)

  return df_long


def get_category_order(df):
  """
  Compute the canonical category display order for all charts.
  Categories are sorted ascending by average time-to-funding.
  Internal capital and Other are excluded from this ordering.
  Returns a default order if data is empty or columns are missing.
  """
  if df.empty or 'category' not in df.columns or 'time_to_funding' not in df.columns:
    return [
      'Grants & non-repayable contributions',
      'Crowdfunding',
      'Community financing',
      'External equity investments',
      'Debt financing',
    ]

  df_filtered = df[~df['category'].isin(['Internal capital', 'Other'])]
  averages = df_filtered.groupby('category')['time_to_funding'].mean().sort_values()
  return averages.index.tolist()


# ==================== MAIN CALLABLE ====================

@anvil.server.callable
def get_all_capital_charts(provinces=None, proj_types=None, stages=None,
                           indigenous_ownership=None, project_scale=None):
  """
  Single server call that returns all chart figures and indicator values at once.

  Loads and processes data once, applies filters, then builds all charts in parallel.
  Returns a dict with keys: box_plot, sankey, time_chart, stacked_bar,
  bottleneck_chart, treemap, scale_pies, indicators.
  """
  # ── Load and process data once ──
  df_raw          = get_data()
  df_capital_mix  = process_capital_mix_data(df_raw)

  # ── Apply filters (three variants for different chart needs) ──
  df_raw_filtered            = apply_filters(df_raw,          provinces, proj_types, stages, indigenous_ownership, project_scale)
  df_capital_filtered        = apply_filters(df_capital_mix,  provinces, proj_types, stages, indigenous_ownership, project_scale)
  df_capital_no_proj_filter  = apply_filters(df_capital_mix,  provinces, None,       stages, indigenous_ownership, project_scale)
  # ^ Sankey excludes proj_type filter so all project types remain visible as destination nodes

  # ── Guard: return empty figures if no data matches the filters ──
  if df_capital_filtered.empty:
    empty_fig = go.Figure()
    empty_fig.update_layout(title="No data available for selected filters")
    empty_indicators = {
      'equity':          {'type': 'N/A', 'source': 'N/A'},
      'debt':            {'interest': 'N/A', 'repayment': 'N/A', 'type': 'N/A', 'source': 'N/A'},
      'grants':          {'type': 'N/A', 'source': 'N/A'},
      'community_finance':{'type': 'N/A', 'source': 'N/A'},
      'crowdfunding':    {'type': 'N/A', 'source': 'N/A'},
    }
    return {k: empty_fig for k in ['box_plot','sankey','time_chart','stacked_bar',
                                   'bottleneck_chart','treemap','scale_pies']} | {'indicators': empty_indicators}

  # ── Compute category order once, reused across multiple charts ──
  category_order          = get_category_order(df_capital_filtered)
  category_order_reversed = list(reversed(category_order))

  return {
    'time_chart':       create_time_chart_internal(df_capital_filtered,       category_order),
    'sankey':           create_sankey_internal(df_capital_no_proj_filter,     proj_types),
    'stacked_bar':      create_stacked_bar_internal(df_capital_filtered,      category_order_reversed),
    'box_plot':         create_box_plot_internal(df_raw_filtered,             category_order_reversed),
    'bottleneck_chart': create_bottleneck_lollipop_internal(df_raw_filtered),
    'treemap':          create_treemap_internal(df_raw_filtered),
    'scale_pies':       create_scale_pies_internal(df_capital_filtered),
    'indicators':       calculate_indicators_internal(df_capital_filtered),
  }


# ==================== CHART CREATION ====================

def create_box_plot_internal(df, category_order):
  """
  Box plot showing the distribution of each financing category's
  contribution to total project costs (as a percentage).
  Individual data points are overlaid on the boxes.
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
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    yaxis_title='', xaxis_title='',
    xaxis=dict(tickangle=20, tickfont=dict(size=10, color='black', family='Arial, sans-serif'), linecolor='grey', showline=True),
    yaxis=dict(ticksuffix="%", tickfont=dict(color='black', family='Arial, sans-serif'), linecolor='grey', showline=True),
    margin=dict(l=0, r=0, t=35, b=0),
    title=dict(text='Average contribution of each financing source to total project costs',
               font=dict(family='Arial, sans-serif', size=16, color='black'),
               x=0.01, xanchor='left', y=0.98, yanchor='top')
  )
  return fig


def create_time_chart_internal(df, category_order):
  """
  Horizontal bar chart showing average time-to-funding for each
  financing category. Internal capital is excluded.
  Bar text labels include category name and value; colour is auto-contrasted.
  """
  df = df[df['category'] != 'Internal capital']
  averages = df.groupby('category')['time_to_funding'].mean().reindex(category_order)
  colors      = [COLOUR_MAPPING.get(c, '#808080') for c in averages.index]
  text_colors = [get_contrast_color(c) for c in colors]

  fig = go.Figure(data=[go.Bar(
    y=averages.index, x=averages.values, orientation='h',
    text=[f'{c}: {v:.1f} years' for c, v in zip(averages.index, averages.values)],
    textposition='inside',
    textfont=dict(family='Arial, sans-serif', color=text_colors),
    marker=dict(color=colors)
  )])
  fig.update_layout(
    yaxis_title='', xaxis_title='', showlegend=False,
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    margin=dict(l=0, r=0, t=35, b=0),
    xaxis=dict(visible=False),
    yaxis=dict(showticklabels=False),
    title=dict(text='Average time to funding',
               font=dict(family='Arial, sans-serif', size=16, color='black'),
               x=0.05, xanchor='left', y=0.98, yanchor='top')
  )
  return fig


def create_sankey_internal(df, proj_types=None):
  """
  Sankey diagram showing capital flow: Funding Source → Category → Project Type.
  Internal capital is handled separately (no upstream source nodes).
  Link colours are semi-transparent versions of the category colour.
  Note: proj_type filter is NOT applied to this chart's dataframe so that all
  project types appear as destination nodes regardless of the active filter.
  """
  df = df.copy()
  for col in ['project_type', 'amount', 'category', 'source']:
    if col not in df.columns:
      df[col] = None

  df['project_type'] = df['project_type'].apply(
    lambda x: x if isinstance(x, list) else ([] if pd.isna(x) else [x])
  )
  df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)

  # Split amount evenly across project types
  df['pt_count'] = df['project_type'].apply(len).replace(0, 1)
  df['amount']   = df['amount'] / df['pt_count']
  df = df.explode('project_type').reset_index(drop=True)

  if proj_types:
    df = df[df['project_type'].isin(proj_types)]
  df = df.drop(columns=['pt_count'], errors='ignore')

  df_internal = df[df['category'] == 'Internal capital'].copy()
  df_other    = df[df['category'] != 'Internal capital'].copy()

  sources_list      = list(df_other['source'].dropna().unique())
  categories_list   = list(df_other['category'].dropna().unique())
  proj_types_list   = list(df['project_type'].dropna().unique())

  # Build node list in column order: sources | categories | Internal capital | project types
  all_nodes = []
  for lst in (sources_list, categories_list, ['Internal capital'], proj_types_list):
    for item in lst:
      if item not in all_nodes:
        all_nodes.append(item)

  node_index = {label: i for i, label in enumerate(all_nodes)}

  agg_s2c = df_other.groupby(['source',   'category'],     dropna=False)['amount'].sum().reset_index()
  agg_c2p = df_other.groupby(['category', 'project_type'], dropna=False)['amount'].sum().reset_index()
  agg_i2p = df_internal.groupby(['project_type'],          dropna=False)['amount'].sum().reset_index()

  def idx(col, val): return node_index.get(val)

  sources = ([idx('source',   r['source'])   for _, r in agg_s2c.iterrows()] +
             [idx('category', r['category']) for _, r in agg_c2p.iterrows()] +
             [node_index.get('Internal capital')] * len(agg_i2p))
  targets = ([idx('category',     r['category'])    for _, r in agg_s2c.iterrows()] +
             [idx('project_type', r['project_type'])for _, r in agg_c2p.iterrows()] +
             [idx('project_type', r['project_type'])for _, r in agg_i2p.iterrows()])
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

  # Add a tiny invisible link into Internal capital so Plotly places it in the middle column
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
    fig.update_layout(title='No data for selected filters')
    return fig

  sv, tv, vv, cv = zip(*valid)

  source_to_category = (df_other.groupby('source')['category'].first().to_dict()
                        if not df_other.empty else {})
  node_colors = []
  for node in all_nodes:
    if node in sources_list:
      node_colors.append(COLOUR_MAPPING.get(source_to_category.get(node), '#808080'))
    elif node in categories_list or node == 'Internal capital':
      node_colors.append(COLOUR_MAPPING.get(node, '#808080'))
    else:
      node_colors.append('#696969')

  fig = go.Figure(data=[go.Sankey(
    arrangement='perpendicular',
    node=dict(align='center', thickness=15,
              line=dict(color='white', width=0),
              label=[str(n) for n in all_nodes],
              color=node_colors,
              hovertemplate='%{label}<br>$%{value:,.0f}<extra></extra>'),
    link=dict(source=list(sv), target=list(tv), value=list(vv), color=list(cv),
              hovertemplate='%{source.label} → %{target.label}<br>$%{value:,.0f}<extra></extra>'),
    textfont=dict(color='black', family='Arial, sans-serif', size=12, weight='bold')
  )])
  fig.update_layout(
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    margin=dict(l=0, r=0, t=35, b=10),
    title=dict(text='Capital flow: Source → Category → Project type',
               font=dict(family='Arial, sans-serif', size=16, color='black'),
               x=0.01, xanchor='left', y=0.98, yanchor='top')
  )
  return fig


def create_stacked_bar_internal(df, category_order):
  """
  Horizontal stacked bar chart showing breakdown of funding sources within each category.
  Excludes Internal capital and Other.
  Colour shades are generated per category (darker = larger share).
  Labels are shown for segments ≥5%; text colour auto-contrasts against the bar colour.
  """
  df = df[~df['category'].isin(['Internal capital', 'Other'])]

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

  color_map = {}
  order_map = {}
  for grp in group_order:
    base  = COLOUR_MAPPING.get(grp, '#808080')
    srcs  = df_grouped[df_grouped['category'] == grp].sort_values('amount', ascending=False)['source'].tolist()
    shades = generate_shades(base, len(srcs))
    for i, src in enumerate(srcs):
      color_map[(grp, src)] = shades[i]
      order_map[(grp, src)] = i

  df_grouped['src_order'] = df_grouped.apply(lambda r: order_map.get((r['category'], r['source']), 999), axis=1)

  all_sources = []
  for grp in group_order:
    for src in df_grouped[df_grouped['category'] == grp].sort_values('src_order')['source']:
      if src not in all_sources:
        all_sources.append(src)

  traces = []
  for src in all_sources:
    sub = df_grouped[df_grouped['source'] == src]
    for _, row in sub.iterrows():
      color = color_map.get((row['category'], src), '#808080')
      label = f'{src}: {row["percentage"]:.1f}%' if row['percentage'] >= 5 else ''
      traces.append(go.Bar(
        name=src,
        y=[row['category']], x=[row['percentage']], orientation='h',
        text=[label], textposition='inside',
        textfont=dict(size=12, color=get_contrast_color(color), family='Arial, sans-serif'),
        marker=dict(color=color),
        hovertemplate='%{fullData.name}<br>%{x:.1f}%<extra></extra>',
        showlegend=False
      ))

  fig = go.Figure(data=traces)
  fig.update_layout(
    barmode='stack', showlegend=False,
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Arial, sans-serif', size=12),
    xaxis=dict(visible=False),
    yaxis=dict(categoryorder='array', categoryarray=list(reversed(group_order))),
    margin=dict(l=0, r=0, t=35, b=0),
    title=dict(text='Funding sources by category',
               font=dict(family='Arial, sans-serif', size=16, color='black'),
               x=0.01, xanchor='left', y=0.98, yanchor='top')
  )
  return fig


def create_bottleneck_lollipop_internal(df):
  """
  Lollipop chart showing the count of projects reporting each key financing bottleneck.
  Only the four pre-selected bottlenecks are displayed.
  Uses dunsparce_colors palette for styling.
  """
  BOTTLENECKS_TO_SHOW = [
    "Difficulty securing up-front capital",
    "Limited access to grants or subsidies",
    "High financing costs",
    "Limited investor interest in community-led projects",
  ]

  counts_df = (df['bottlenecks'].explode().value_counts()
    .reset_index().rename(columns={'index':'bottleneck','bottlenecks':'count'}))
  counts_df.columns = ['bottleneck', 'count']
  counts_df = (counts_df[counts_df['bottleneck'].isin(BOTTLENECKS_TO_SHOW)]
    .sort_values('count', ascending=True))

  bottlenecks = counts_df['bottleneck'].tolist()
  counts      = counts_df['count'].tolist()
  y_pos       = list(range(len(bottlenecks)))
  color       = dunsparce_colors[1]

  fig = make_subplots()

  for i, (label, count) in enumerate(zip(bottlenecks, counts)):
    # Horizontal line
    fig.add_scatter(x=[0, count], y=[i, i], mode='lines',
                    line=dict(color=color, width=6), showlegend=False, hoverinfo='skip')
    # Category label above the line
    fig.add_annotation(text=label, x=0.1, y=i + 0.37,
                       xanchor='left', yanchor='middle', showarrow=False,
                       font=dict(family='Arial, sans-serif', size=14, color=dunsparce_colors[5]))
    # Count label on the dot
    fig.add_annotation(text=f'<b>{count}</b>', x=count, y=i,
                       xanchor='center', yanchor='middle', showarrow=False,
                       font=dict(color='white', family='Arial, sans-serif', size=16))

  # Dots at the end of each line
  fig.add_scatter(x=counts, y=y_pos, mode='markers',
                  marker=dict(size=30, color=color), showlegend=False,
                  hovertemplate='<b>%{text}</b><br>Count: %{x}<extra></extra>',
                  text=bottlenecks)

  fig.update_xaxes(visible=False, range=[0, max(counts) * 1.15] if counts else [0, 10],
                   showgrid=False)
  fig.update_yaxes(visible=False, showgrid=False)
  fig.update_layout(
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Arial, sans-serif', size=12, color='#00504a'),
    margin=dict(l=0, r=0, t=35, b=0),
    title=dict(text='Financing Bottlenecks',
               font=dict(family='Arial, sans-serif', size=16, color='#00504a'),
               x=0.01, xanchor='left', y=0.98, yanchor='top')
  )
  return fig


def create_treemap_internal(df):
  """
  Treemap showing how frequently each financing mechanism/source is used,
  grouped by category. Size = number of projects using that source.
  Text colour auto-contrasts against the tile colour.
  """
  if df.empty or 'financing_mech' not in df.columns:
    fig = go.Figure()
    fig.update_layout(title='No data available for selected filters')
    return fig

  rows = []
  for _, row in df.iterrows():
    for item in (row.get('financing_mech') or []):
      rows.append({
        'record_id': row.get('record_id'),
        'source':    item.get('source'),
        'category':  standardize_category_name(item.get('category')),
      })

  df_long = pd.DataFrame(rows)
  if df_long.empty:
    fig = go.Figure()
    fig.update_layout(title='No financing mechanism data available')
    return fig

  df_long['source'] = df_long['source'].replace({
    'Other': 'Other/Unknown', 'Not sure': 'Other/Unknown',
    'Aggregate total': 'Other/Unknown', 'Aggregate Total': 'Other/Unknown',
    "Don't know": 'Other/Unknown', 'N/A': 'Other/Unknown',
  })
  mask = df_long['source'] == 'Other/Unknown'
  df_long.loc[mask, 'source'] = df_long.loc[mask, 'source'] + '-' + df_long.loc[mask, 'category']

  df_grouped = df_long.groupby(['source', 'category']).size().reset_index(name='count')
  if df_grouped.empty:
    fig = go.Figure()
    fig.update_layout(title='No financing mechanism data available')
    return fig

  category_totals = df_grouped.groupby('category')['count'].sum().to_dict()

  labels, parents, values, colors, text_colors = [], [], [], [], []

  for cat in df_grouped['category'].unique():
    labels.append(cat)
    parents.append('')
    values.append(category_totals[cat])
    col = COLOUR_MAPPING.get(cat, '#808080')
    colors.append(col)
    text_colors.append(get_contrast_color(col))

  for _, row in df_grouped.iterrows():
    labels.append(wrap_text(row['source'], width=20) if row['source'] else row['source'])
    parents.append(row['category'])
    values.append(row['count'])
    col = COLOUR_MAPPING.get(row['category'], '#808080')
    colors.append(col)
    text_colors.append(get_contrast_color(col))

  fig = go.Figure(go.Treemap(
    labels=labels, parents=parents, values=values,
    branchvalues='total',
    marker=dict(colors=colors, line=dict(color='white', width=2)),
    textfont=dict(family='Arial, sans-serif', size=12, color=text_colors),
    textposition='middle center',
    hovertemplate='<b>%{label}</b><br>Count: %{value}<extra></extra>'
  ))
  fig.update_layout(
    font=dict(family='Arial, sans-serif', size=14, color='black'),
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=0, r=0, t=35, b=0),
    title=dict(text='Use of Funding & Financing Mechanisms',
               font=dict(family='Arial, sans-serif', size=16, color='black'),
               x=0.01, xanchor='left', y=0.98, yanchor='top')
  )
  return fig


def create_scale_pies_internal(df):
  """
  Row of pie charts — one per project scale — showing the funding category mix.
  Scales are shown in order from smallest to largest.
  Subtitle on each pie shows the scale label and number of projects.
  """
  SCALE_ORDER = [
    "Micro (< $100K)", "Small ($100K-$1M)", "Medium ($1M-$5M)",
    "Large ($5M-$25M)", "Very Large ($25M-$100M)", "Mega (> $100M)"
  ]
  scales = [s for s in SCALE_ORDER if s in df['project_scale'].values]
  if not scales:
    fig = go.Figure()
    fig.update_layout(title='No data available')
    return fig

  fig = make_subplots(
    rows=1, cols=len(scales),
    specs=[[{'type': 'domain'}] * len(scales)],
    subplot_titles=scales
  )

  for i, scale in enumerate(scales):
    sub     = df[df['project_scale'] == scale]
    grouped = sub.groupby('category', as_index=False)['amount'].sum()
    colors  = [COLOUR_MAPPING.get(c, '#808080') for c in grouped['category']]

    fig.add_trace(go.Pie(
      labels=grouped['category'], values=grouped['amount'], name=scale,
      marker=dict(colors=colors),
      texttemplate='%{percent:.1%}', textposition='inside',
      textfont=dict(family='Arial, sans-serif', size=10, color='white'),
      sort=False,
      hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>',
    ), row=1, col=i + 1)

    # Update subtitle to include project count
    n = sub['record_id'].nunique()
    fig.layout.annotations[i].update(
      text=f"{scale}<br>({n} projects)",
      font=dict(family='Arial, sans-serif', size=14, color='black'),
      y=0.9
    )

  fig.update_layout(
    showlegend=True,
    legend=dict(orientation='h', y=0.01, x=0.5, xanchor='center'),
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    margin=dict(l=0, r=0, t=35, b=0),
    title=dict(text='Funding distribution by project scale',
               font=dict(family='Arial, sans-serif', size=16, color='black'),
               x=0.01, xanchor='left', y=0.99, yanchor='top')
  )
  return fig


# ==================== INDICATORS CALCULATION ====================

def _top_source_and_mechanism(df, category_name):
  """
  Helper used by calculate_indicators_internal.
  Returns the most common source and item_type for a given category,
  expressed as '(X% projects)' strings.
  """
  sub = df[df['category'] == category_name]
  if sub.empty:
    return {'type': 'N/A', 'source': 'N/A'}

  n = sub['record_id'].nunique()

  src_counts  = sub.groupby('source')['record_id'].nunique()
  mech_counts = sub.groupby('item_type')['record_id'].nunique()

  top_src  = src_counts.idxmax()  if not src_counts.empty  else 'N/A'
  top_mech = mech_counts.idxmax() if not mech_counts.empty else 'N/A'

  return {
    'type':   f"{top_mech} ({mech_counts.max() / n * 100:.0f}% projects)" if not mech_counts.empty else 'N/A',
    'source': f"{top_src}  ({src_counts.max()  / n * 100:.0f}% projects)" if not src_counts.empty  else 'N/A',
  }


def calculate_indicators_internal(df):
  """
  Calculate summary indicator values for each financing category.
  Debt gets extra fields for interest rate and repayment period.
  Returns a dict keyed by category name.
  """
  results = {
    'equity':           _top_source_and_mechanism(df, 'External equity investments'),
    'grants':           _top_source_and_mechanism(df, 'Grants & non-repayable contributions'),
    'community_finance':_top_source_and_mechanism(df, 'Community financing'),
    'crowdfunding':     _top_source_and_mechanism(df, 'Crowdfunding'),
  }

  # ── Debt needs additional interest rate + repayment period fields ──
  debt_df = df[df['category'] == 'Debt financing']
  if debt_df.empty:
    results['debt'] = {'interest': 'N/A', 'repayment': 'N/A', 'type': 'N/A', 'source': 'N/A'}
  else:
    n = debt_df['record_id'].nunique()

    # Average interest rate
    def parse_rate(s):
      if pd.isna(s): return np.nan
      s = str(s).strip().replace('%', '')
      if '-' in s:
        parts = s.split('-')
        try: return (float(parts[0]) + float(parts[1])) / 2
        except: return np.nan
      try: return float(s)
      except: return np.nan

    rates = debt_df[debt_df['debt_interest'].notna()]['debt_interest'].apply(parse_rate).dropna()
    avg_interest = f"{rates.mean():.1f}%" if not rates.empty else 'N/A'

    # Most common repayment period
    rep = debt_df[debt_df['repayment_period'].notna()]
    if rep.empty:
      repayment_text = 'N/A'
    else:
      rep_counts     = rep.groupby('repayment_period')['record_id'].nunique()
      common_rep     = rep_counts.idxmax()
      repayment_text = f"{common_rep} ({rep_counts.max() / n * 100:.0f}% projects)"

    debt_base = _top_source_and_mechanism(df, 'Debt financing')
    results['debt'] = {
      'interest':  avg_interest,
      'repayment': repayment_text,
      'type':      debt_base['type'],
      'source':    debt_base['source'],
    }

  return results


# ==================== EXPORT CALLABLE ====================

@anvil.server.callable
def export_capital_chart(chart_key, img_b64, active_filters):
  """
  Receives a base64 PNG captured by the client browser,
  passes it to Export_Utils for logo + filter decoration,
  and returns a BlobMedia for anvil.download().
  """
  return export_figure_from_bytes(
    img_b64,
    active_filters,
    filename=f"{chart_key}_export.png"
  )