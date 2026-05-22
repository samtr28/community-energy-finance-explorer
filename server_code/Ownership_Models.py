"""
Ownership.py — Server module for the Ownership page
====================================================
Charts
------
ownership_treemap        : Dollar value of ownership by type — (owner % × project cost).
scale_pies               : Same dollar-value calc broken down by project scale.
indigenous_pie           : Count of survey responses at each level of Indigenous ownership.
ownership_boxplot        : Spread of ownership % by owner category.
ownership_tiers_hist.    : Count of owner entries per stake bracket, per category.
lollipop_chart (key)     : Governance bottlenecks, split by single vs multiple ownership.
all_financing_heatmap    : Count of responses where owner category + financing co-occur.
collaboration_heatmap    : How often owner categories co-occur on multi-owner projects.
single_owner_breakdown   : Single-owner projects by category, stacked by owner type.
multi_owner_semicircles  : Per-project semicircle of owners, shaded by owner type.

Key fixes vs previous version
------------------------------
1. apply_filters          — project_scale normalised with .astype(str).str.strip() before
                            any comparison, fixing Mega rows being silently dropped from
                            df_owners_filtered due to Categorical dtype mismatch.
2. process_owners_data    — project_scale explicitly cast to stripped string when building
                            the flat owners frame, so dtype is consistent with the filter.
3. create_ownership_treemap_internal
                          — CATEGORY_COLOUR_SCHEME['Other'] direct key access replaced with
                            a safe .get() fallback so projects with owner_category='Other'
                            (e.g. record 105 Columbia Basin Trust) no longer crash the chart.
4. create_multi_owner_semicircles_internal
                          — Threshold restored to sum > 90 (lenient) from the too-strict
                            95–105 range that was silently dropping valid projects.
                          — Simple (o.get('owner_percent') or 0) check reinstated instead of
                            pd.to_numeric which was filtering out valid numeric values.
"""

import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import textwrap
import math
from itertools import combinations
from plotly.subplots import make_subplots

from .config import (
COLOUR_MAPPING, gradient_palette, dunsparce_colors,
FONT_FAMILY, FONT_SIZE, FONT_COLOR,
get_owner_type_colors_categorical, CATEGORY_COLOUR_SCHEME, CATEGORY_ORDER_OWNERS,
)
from .Global_Server_Functions import get_data
from .Export_Utils import apply_display_template, export_figure_from_bytes


# ==================== UTILITY FUNCTIONS ====================

def wrap_text(text, width=15):
  return '<br>'.join(textwrap.wrap(str(text), width=width))


def get_contrast_color(hex_color):
  if not hex_color or not hex_color.startswith('#'):
    return 'white'
  hex_color = hex_color.lstrip('#')
  r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
  return 'black' if (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.5 else 'white'


def _owner_type_category_pairs(df_owners):
  return list(
    df_owners[['owner_type', 'owner_category']]
      .drop_duplicates()
      .itertuples(index=False, name=None)
  )

# Safe colour fallback used throughout — avoids KeyError when owner_category
# values arrive that aren't defined in CATEGORY_COLOUR_SCHEME (e.g. 'Other').
_FALLBACK_SCHEME = {'base': '#808080', 'shades': ['#808080']}


def _cat_colour(cat):
  """Return the base hex colour for an owner_category, never raising KeyError."""
  scheme = CATEGORY_COLOUR_SCHEME.get(cat) or _FALLBACK_SCHEME
  return scheme.get('base', '#808080')


# ==================== DATA FILTERING ====================

def apply_filters(df, provinces=None, proj_types=None, stages=None,
                  indigenous_ownership=None, project_scale=None):
  """
  Apply user-selected filters to a dataframe. Returns a filtered copy.

  project_scale is normalised to plain stripped strings before comparison.
  This handles the case where df_raw has a pandas Categorical dtype for
  project_scale while df_owners (built row-by-row) has object dtype — without
  normalisation, .isin() silently fails to match Mega rows in df_owners_filtered.
  """
  if df.empty:
    return df
  df = df.copy()

  if 'project_scale' in df.columns:
    df['project_scale'] = df['project_scale'].astype(str).str.strip()

  if provinces:
    df = df[df['province'].isin(provinces)]
  if proj_types:
    df = df[df['project_type'].apply(
      lambda x: any(t in x for t in proj_types) if isinstance(x, list) else False
    )]
  if stages:
    df = df[df['stage'].isin(stages)]
  if indigenous_ownership:
    df = df[df['indigenous_ownership'].isin(indigenous_ownership)]
  if project_scale:
    clean = [str(s).strip() for s in project_scale]
    df = df[df['project_scale'].isin(clean)]
  return df


# ==================== DATA PROCESSING ====================

def process_owners_data(df):
  """
  Explode the owners list into one row per owner entry.
  project_scale is cast to a plain stripped string so dtype is consistent
  regardless of whether the source column is Categorical or object.
  """
  rows = []
  for _, row in df.iterrows():
    owners = row.get('owners') or []
    for owner in owners:
      ps = row.get('project_scale')
      rows.append({
        'record_id':            row.get('record_id'),
        'owner_name':           owner.get('owner_name'),
        'owner_type':           owner.get('owner_type'),
        'owner_category':       owner.get('owner_category') or 'Other',
        'owner_percent':        owner.get('owner_percent'),
        'project_type':         row.get('project_type'),
        'project_name':         row.get('project_name'),
        'province':             row.get('province'),
        'project_scale':        str(ps).strip() if pd.notna(ps) else None,
        'stage':                row.get('stage'),
        'indigenous_ownership': row.get('indigenous_ownership'),
        'total_cost':           row.get('total_cost'),
      })
  return pd.DataFrame(rows)


# ==================== MAIN CALLABLE ====================

@anvil.server.callable
def get_all_ownership_charts(provinces=None, proj_types=None, stages=None,
                             indigenous_ownership=None, project_scale=None):
  """
  Single server call returning all chart figures.
  Data is loaded and processed once, shared across all chart builders.
  Each builder is wrapped individually so one failure doesn't silence the rest.
  """
  df_raw    = get_data()
  df_owners = process_owners_data(df_raw)

  df_raw_filtered    = apply_filters(df_raw,    provinces, proj_types, stages, indigenous_ownership, project_scale)
  df_owners_filtered = apply_filters(df_owners, provinces, proj_types, stages, indigenous_ownership, project_scale)

  def _empty(msg='No data available for selected filters'):
    f = go.Figure()
    f.update_layout(title=dict(text=msg))
    return f

  # Build each chart individually so one exception doesn't kill all charts
  def _build(key, fn, fallback_df):
    if fallback_df.empty:
      return _empty()
    try:
      return fn()
    except Exception as e:
      import traceback
      print(f'[Ownership] ERROR in {key}:\n{traceback.format_exc()}')
      return _empty(f'Error building {key}')

  charts = {
    # ── Charts that use the flat owners frame ──
    'ownership_treemap':         _build('ownership_treemap',         lambda: create_ownership_treemap_internal(df_owners_filtered),         df_owners_filtered),
    'scale_pies':                _build('scale_pies',                lambda: create_ownership_scale_pies_internal(df_owners_filtered),      df_owners_filtered),
    'indigenous_pie':            _build('indigenous_pie',            lambda: create_indigenous_ownership_stacked_internal(df_owners_filtered), df_owners_filtered),
    'ownership_boxplot':         _build('ownership_boxplot',         lambda: create_ownership_boxplot_internal(df_owners_filtered),          df_owners_filtered),
    'ownership_tiers_histogram': _build('ownership_tiers_histogram', lambda: create_ownership_tiers_histogram_internal(df_owners_filtered),  df_owners_filtered),
    # ── Charts that use the raw per-response frame ──
    'lollipop_chart':            _build('lollipop_chart',            lambda: create_governance_bottlenecks_internal(df_raw_filtered),        df_raw_filtered),
    'all_financing_heatmap':     _build('all_financing_heatmap',     lambda: create_ownership_all_financing_heatmap_internal(df_raw_filtered), df_raw_filtered),
    'collaboration_heatmap':     _build('collaboration_heatmap',     lambda: create_collaboration_heatmap_internal(df_raw_filtered),         df_raw_filtered),
    'single_owner_breakdown':    _build('single_owner_breakdown',    lambda: create_single_owner_breakdown_internal(df_raw_filtered),        df_raw_filtered),
    'multi_owner_semicircles':   _build('multi_owner_semicircles',   lambda: create_multi_owner_semicircles_internal(df_raw_filtered),       df_raw_filtered),
  }

  # Apply display template to all charts except semicircles, which uses a
  # mixed pie+scatter layout that apply_display_template breaks.
  result = {}
  for k, v in charts.items():
    if k == 'multi_owner_semicircles':
      result[k] = v   # no template — figure manages its own styling
    else:
      result[k] = apply_display_template(v)
  return result


# ==================== CHART CREATION ====================

def create_ownership_treemap_internal(df_owners):
  df_val = df_owners.copy()
  df_val['owner_percent'] = pd.to_numeric(df_val['owner_percent'], errors='coerce')
  df_val['total_cost']    = pd.to_numeric(df_val['total_cost'],    errors='coerce')
  df_val['ownership_value'] = (df_val['owner_percent'] / 100) * df_val['total_cost']
  df_val = df_val.dropna(subset=['ownership_value'])

  if df_val.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No ownership value data available'))
    return fig

  value_data   = df_val.groupby(['owner_type', 'owner_category'], as_index=False)['ownership_value'].sum()
  owner_colors = get_owner_type_colors_categorical(_owner_type_category_pairs(df_owners))
  cat_totals   = value_data.groupby('owner_category')['ownership_value'].sum()

  ids_list, labels, parents, values, colors_list = [], [], [], [], []

  # Category (root) nodes — ID prefixed so 'Other' category ≠ 'Other' type
  for cat, total in cat_totals.items():
    ids_list.append(f'cat::{cat}')
    labels.append(cat)
    parents.append('')
    values.append(total)
    colors_list.append(_cat_colour(cat))

    # Owner-type (leaf) nodes — parent references the category ID above
  for _, row in value_data.iterrows():
    ids_list.append(f'type::{row["owner_category"]}::{row["owner_type"]}')
    labels.append(wrap_text(row['owner_type'], width=20))
    parents.append(f'cat::{row["owner_category"]}')
    values.append(row['ownership_value'])
    colors_list.append(owner_colors.get(row['owner_type'], '#808080'))

  fig = go.Figure(go.Treemap(
    ids=ids_list,
    labels=labels, parents=parents, values=values,
    branchvalues='total',
    texttemplate='<b>%{label}</b><br>%{percentRoot:.1%}',
    hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<extra></extra>',
    marker=dict(colors=colors_list, line=dict(width=2, color='white')),
  ))
  fig.update_layout(
    title=dict(text='Ownership composition of community energy projects'),
    margin=dict(t=50, b=0, l=0, r=0),
  )
  return fig


def create_ownership_scale_pies_internal(df_owners):
  SCALE_ORDER = [
    'Micro (< $100K)', 'Small ($100K-$1M)', 'Medium ($1M-$5M)',
    'Large ($5M-$25M)', 'Very Large ($25M-$100M)', 'Mega (> $100M)'
  ]
  scales = [s for s in SCALE_ORDER if s in df_owners['project_scale'].values]
  if not scales:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No data available'))
    return fig

  owner_type_colors = get_owner_type_colors_categorical(_owner_type_category_pairs(df_owners))
  cats_present      = [c for c in CATEGORY_ORDER_OWNERS if c in df_owners['owner_category'].unique()]
  fig    = go.Figure()
  n_pies = len(scales)

  for i, scale in enumerate(scales):
    sub     = df_owners[df_owners['project_scale'] == scale].copy()
    n       = sub['record_id'].nunique()
    sub['owner_percent'] = pd.to_numeric(sub['owner_percent'], errors='coerce')
    sub['total_cost']    = pd.to_numeric(sub['total_cost'],    errors='coerce')
    sub['ownership_value'] = (sub['owner_percent'] / 100) * sub['total_cost']

    value_grouped = sub.groupby(['owner_type', 'owner_category'], as_index=False)['ownership_value'].sum()
    value_grouped['cat_order'] = value_grouped['owner_category'].apply(
      lambda c: CATEGORY_ORDER_OWNERS.index(c) if c in CATEGORY_ORDER_OWNERS else 999
    )
    value_grouped.sort_values(['cat_order', 'owner_type'], inplace=True)
    value_grouped.reset_index(drop=True, inplace=True)

    denom = value_grouped['ownership_value'].sum()
    value_grouped['pct'] = (value_grouped['ownership_value'] / denom * 100) if denom else 0
    value_grouped['text_display'] = value_grouped['pct'].apply(
      lambda x: f'{x:.1f}%' if x >= 5 else ''
    )

    pad     = 0.01
    x_start = i / n_pies + pad
    x_end   = (i + 1) / n_pies - pad
    domain  = dict(x=[x_start, x_end], y=[0.25, 1.0])
    title_style = dict(
      text=f'{scale}<br>({n} projects)',
      font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),
      position='top center',
    )

    fig.add_trace(go.Pie(
      labels=value_grouped['owner_type'],
      values=value_grouped['ownership_value'],
      domain=domain, title=title_style,
      marker=dict(colors=[
        owner_type_colors.get(ot, '#808080') for ot in value_grouped['owner_type']
      ]),
      sort=False, direction='clockwise',
      textinfo='text', text=value_grouped['text_display'],
      hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<br>%{percent} of value<extra></extra>',
      showlegend=False, visible=True,
    ))

  # ── Custom legend swatches ──
  shades_per_category = {}
  for cat in cats_present:
    types_in_cat = sorted(df_owners[df_owners['owner_category'] == cat]['owner_type'].unique())
    shades_per_category[cat] = [
      owner_type_colors[ot] for ot in types_in_cat if ot in owner_type_colors
    ]

  shapes, annotations = [], []
  swatch_width   = 0.04;  swatch_height  = 0.025
  label_padding  = 0.006; entry_padding  = 0.025; char_width_est = 0.0085

  def entry_width(cat):
    return swatch_width + label_padding + len(cat) * char_width_est

  active_cats  = [c for c in cats_present if shades_per_category.get(c)]
  total_width  = (sum(entry_width(c) for c in active_cats)
                  + entry_padding * max(0, len(active_cats) - 1))
  current_x    = (1 - total_width) / 2
  y_center     = 0.20
  y_swatch_bot = y_center - swatch_height / 2
  y_swatch_top = y_center + swatch_height / 2

  for cat in active_cats:
    shades    = shades_per_category[cat]
    seg_width = swatch_width / len(shades)
    for k, shade in enumerate(shades):
      shapes.append(dict(
        type='rect', xref='paper', yref='paper',
        x0=current_x + k * seg_width, x1=current_x + (k + 1) * seg_width,
        y0=y_swatch_bot, y1=y_swatch_top, fillcolor=shade, line=dict(width=0),
      ))
    shapes.append(dict(
      type='rect', xref='paper', yref='paper',
      x0=current_x, x1=current_x + swatch_width,
      y0=y_swatch_bot, y1=y_swatch_top,
      fillcolor='rgba(0,0,0,0)', line=dict(color='lightgray', width=0.5),
    ))
    annotations.append(dict(
      xref='paper', yref='paper',
      x=current_x + swatch_width + label_padding, y=y_center,
      xanchor='left', yanchor='middle', text=cat, showarrow=False,
      font=dict(family=FONT_FAMILY, size=11, color=FONT_COLOR),
    ))
    current_x += entry_width(cat) + entry_padding

  fig.update_layout(
    title=dict(text='Ownership composition by project scale'),
    showlegend=False, shapes=shapes, annotations=annotations,
    margin=dict(t=50, b=0, l=0, r=0),
  )
  return fig


def create_ownership_boxplot_internal(df_owners):
  df_plot = df_owners[df_owners['owner_percent'] > 0].copy()
  if df_plot.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No ownership data available'))
    return fig

  type_order = (
    df_plot.groupby('owner_category')['owner_percent']
      .median().sort_values(ascending=False).index.tolist()
  )
  color_map = {cat: _cat_colour(cat) for cat in type_order}

  fig = px.box(
    df_plot, x='owner_category', y='owner_percent', points='all',
    color='owner_category', color_discrete_map=color_map,
    category_orders={'owner_category': type_order},
    hover_data=['project_name', 'owner_type'],
  )
  fig.update_layout(
    showlegend=False, yaxis_title='', xaxis_title='',
    xaxis=dict(tickangle=20, linecolor='grey', showline=True),
    yaxis=dict(ticksuffix='%', linecolor='grey', showline=True),
    margin=dict(l=0, r=0, b=0, t=50),
    title=dict(text='Typical ownership stake by owner category'),
  )
  return fig


def create_ownership_tiers_histogram_internal(df_owners):
  TIERS = ['<25%', '25–50%', '51–74%', '75–99%', '100%']
  TIER_COLORS = {
    '<25%':  '#c9e4ca', '25–50%': '#87bba2', '51–74%': '#55828b',
    '75–99%':'#3b6064', '100%':   '#27474e',
  }

  def assign_tier(pct):
    if pct < 25:  return '<25%'
    if pct <= 50: return '25–50%'
    if pct <= 74: return '51–74%'
    if pct <= 99: return '75–99%'
    return '100%'

  df_plot = df_owners[df_owners['owner_percent'] > 0].copy()
  if df_plot.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No ownership data available'))
    return fig
  df_plot['tier'] = df_plot['owner_percent'].apply(assign_tier)

  cat_order = (
    df_plot.groupby('owner_category')['owner_percent']
      .median().sort_values(ascending=False).index.tolist()
  )

  n_cats = len(cat_order)
  fig = make_subplots(
    rows=1, cols=n_cats, shared_yaxes=True,
    subplot_titles=cat_order, horizontal_spacing=0.04,
  )

  for col_i, cat in enumerate(cat_order, start=1):
    sub         = df_plot[df_plot['owner_category'] == cat]
    tier_counts = sub['tier'].value_counts().reindex(TIERS, fill_value=0)
    for tier in TIERS:
      count = tier_counts[tier]
      fig.add_trace(go.Bar(
        x=[tier], y=[count], name=tier, marker_color=TIER_COLORS[tier],
        showlegend=(col_i == 1),
        hovertemplate=f'<b>{cat}</b><br>{tier}: {count}<extra></extra>',
      ), row=1, col=col_i)
    fig.update_xaxes(tickangle=45, tickfont=dict(size=9), row=1, col=col_i)

  fig.update_yaxes(title_text='Owner entries', col=1, showgrid=True, gridcolor='#f0f0f0')
  fig.update_layout(
    barmode='group',
    title=dict(text='Ownership stake distribution by category'),
    legend=dict(title='Stake bracket', traceorder='normal'),
    margin=dict(l=0, r=0, b=0, t=75),
    font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),
  )
  return fig


def create_indigenous_ownership_stacked_internal(df_owners):
  ownership_counts = (
    df_owners.groupby('indigenous_ownership')['record_id']
      .nunique().reset_index()
  )
  ownership_counts.columns = ['Category', 'Count']
  total = ownership_counts['Count'].sum()
  if not total:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No data available'))
    return fig

  ownership_counts['Percentage'] = (ownership_counts['Count'] / total) * 100
  order = [
    'Not sure', 'No Indigenous ownership',
    'Minority Indigenous owned (1-49%)', 'Half Indigenous owned (50%)',
    'Majority Indigenous owned (51-99%)', 'Wholly Indigenous owned (100%)',
  ]
  ownership_counts['Category'] = pd.Categorical(
    ownership_counts['Category'], categories=order, ordered=True
  )
  ownership_counts = ownership_counts.sort_values('Category').reset_index(drop=True)
  colors = [gradient_palette[i * 2] for i in range(len(ownership_counts))][::-1]

  fig = go.Figure()
  for i, row in ownership_counts.iterrows():
    fig.add_trace(go.Bar(
      x=[''], y=[row['Count']], name=row['Category'], orientation='v',
      text=f"<b>{row['Percentage']:.1f}%  -  {row['Category']}</b>",
      textposition='inside', marker=dict(color=colors[i]),
      hovertemplate=(
        f"<b>{row['Category']}</b><br>"
        f"Responses: {row['Count']}<br>{row['Percentage']:.1f}%<extra></extra>"
      ),
    ))
  fig.update_layout(
    title=dict(text='Indigenous project ownership'),
    barmode='stack', showlegend=False,
    xaxis=dict(visible=False), yaxis=dict(visible=False),
    margin=dict(t=50, b=0, l=0, r=0),
  )
  return fig


def create_governance_bottlenecks_internal(df):
  KEEP = [
    'Challenges with project governance or decision-making',
    'Conflicts among stakeholders or partners',
    'Limited community engagement or support',
  ]
  rows = []
  for _, row in df.iterrows():
    bottlenecks = row.get('bottlenecks') or []
    owners      = row.get('owners') or []
    cats        = {o.get('owner_category') or 'Other' for o in owners}
    ownership_type = 'Single owner' if len(cats) <= 1 else 'Multiple owners'
    for b in bottlenecks:
      if b in KEEP:
        rows.append({'bottleneck': b, 'ownership_type': ownership_type})

  if not rows:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No governance bottleneck data available'))
    return fig

  grouped = (
    pd.DataFrame(rows)
      .groupby(['bottleneck', 'ownership_type']).size()
      .reset_index(name='count')
  )

  fig = px.bar(
    grouped, y='bottleneck', x='count', color='ownership_type',
    barmode='stack', orientation='h',
    labels={'bottleneck': '', 'count': 'Responses', 'ownership_type': ''},
    color_discrete_map={'Single owner': '#55828b', 'Multiple owners': '#e07b3a'},
    category_orders={'bottleneck': KEEP},
  )
  fig.update_yaxes(automargin=True, tickmode='linear')
  fig.update_layout(
    title=dict(text='Governance bottlenecks'),
    legend=dict(orientation='h', yanchor='bottom', y=-0.3, xanchor='center', x=0.5),
    margin=dict(l=0, r=0, t=50, b=0),
  )
  return fig


def _build_ownership_financing_pairs(df, direct_only=True):
  pairs = []
  for _, row in df.iterrows():
    owners    = row.get('owners') or []
    financing = row.get('financing_mech') or []
    if not owners or not financing:
      continue
    total_cost = pd.to_numeric(row.get('total_cost'), errors='coerce') or 0
    rid        = row.get('record_id')

    cat_percents = {}
    for o in owners:
      cat = o.get('owner_category') or 'Unknown'
      pct = pd.to_numeric(o.get('owner_percent'), errors='coerce') or 0
      cat_percents[cat] = cat_percents.get(cat, 0) + pct

    if direct_only:
      fin_items = [f for f in financing
                   if f.get('parent') == 'Direct sources of capital' and f.get('category')]
    else:
      fin_items = [f for f in financing if f.get('category')]

    finance_cats = list({f.get('category') for f in fin_items})
    if not finance_cats:
      continue
    for oc, pct_sum in cat_percents.items():
      for fc in finance_cats:
        pairs.append({
          'record_id':    rid,
          'owner_category': oc,
          'finance_category': fc,
          'owner_dollar': (pct_sum / 100) * total_cost,
        })
  return pd.DataFrame(pairs) if pairs else pd.DataFrame()


def create_ownership_all_financing_heatmap_internal(df):
  """Heatmap: owner category × financing mechanism co-occurrence. Blue palette."""
  pairs_df = _build_ownership_financing_pairs(df, direct_only=False)
  if pairs_df.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No ownership-financing data available'))
    return fig

  count_data = (
    pairs_df.groupby(['owner_category', 'finance_category'])['record_id']
      .nunique().reset_index(name='count')
  )

  owner_order   = (count_data.groupby('owner_category')['count'].sum()
    .sort_values(ascending=False).index.tolist())
  finance_order = (count_data.groupby('finance_category')['count'].sum()
    .sort_values(ascending=False).index.tolist())

  finance_wrap_map = {f: wrap_text(f, width=35) for f in finance_order}
  finance_order_w  = [finance_wrap_map[f] for f in finance_order]
  count_data['finance_w'] = count_data['finance_category'].map(finance_wrap_map)

  count_pivot = (
    count_data
      .pivot_table(index='finance_w', columns='owner_category',
                   values='count', fill_value=0)
      .reindex(index=finance_order_w, columns=owner_order, fill_value=0)
  )

  max_val = count_pivot.values.max() or 1
  annotations = []
  for fi, row_label in enumerate(count_pivot.index):
    for oi, col_label in enumerate(count_pivot.columns):
      val = count_pivot.iloc[fi, oi]
      if val <= 0:
        continue
      annotations.append(dict(
        x=col_label, y=row_label, text=f'<b>{int(val)}</b>',
        showarrow=False, xref='x', yref='y',
        font=dict(family=FONT_FAMILY, size=10,
                  color='white' if val > max_val * 0.5 else FONT_COLOR),
      ))

  fig = go.Figure(go.Heatmap(
    z=count_pivot.values, x=owner_order, y=finance_order_w,
    colorscale=[[0, '#f7f9fc'], [1, '#005694']],   # ← blue
    showscale=False, xgap=2, ygap=2,
    hovertemplate='<b>%{y}</b><br>Owner: %{x}<br>Responses: %{z}<extra></extra>',
  ))
  fig.update_layout(
    title=dict(text='All financing mechanisms by ownership category', x=0, xanchor='left'),
    annotations=annotations,
    margin=dict(l=0, b=0, t=50, r=0),
    font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),
    xaxis=dict(title='', tickangle=-20, side='bottom'),
    yaxis=dict(title='', autorange='reversed'),
  )
  return fig






def create_collaboration_heatmap_internal(df):
  all_cats = set()
  project_cat_sets = []
  for _, row in df.iterrows():
    owners = row.get('owners') or []
    if len(owners) < 2:
      continue
    cats = sorted({o.get('owner_category') or 'Other' for o in owners})
    project_cat_sets.append(cats)
    all_cats.update(cats)

  if not project_cat_sets:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No multi-owner projects for selected filters'))
    return fig

  ordered  = [c for c in CATEGORY_ORDER_OWNERS if c in all_cats]
  ordered += [c for c in sorted(all_cats) if c not in ordered]

  matrix = pd.DataFrame(0, index=ordered, columns=ordered)
  for cats in project_cat_sets:
    for a, b in combinations(cats, 2):
      matrix.loc[a, b] += 1
      matrix.loc[b, a] += 1
    if len(cats) == 1:
      matrix.loc[cats[0], cats[0]] += 1

  max_val = matrix.values.max() or 1
  annotations = []
  for yl in ordered:
    for xl in ordered:
      val = matrix.loc[yl, xl]
      if val <= 0:
        continue
      annotations.append(dict(
        x=xl, y=yl, text=f'<b>{int(val)}</b>', showarrow=False,
        xref='x', yref='y',
        font=dict(family=FONT_FAMILY, size=11,
                  color='white' if val > max_val * 0.5 else FONT_COLOR),
      ))

  fig = go.Figure(go.Heatmap(
    z=matrix.values, x=ordered, y=ordered,
    colorscale=[[0, '#f7f9fc'], [1, dunsparce_colors[1]]],
    showscale=False, xgap=3, ygap=3,
    hovertemplate='%{y} + %{x}<br>Projects: %{z}<extra></extra>',
  ))
  fig.update_layout(
    title=dict(text=f'Owner category collaboration ({len(project_cat_sets)} multi-owner projects)'),
    annotations=annotations,
    margin=dict(l=0, r=0, t=50, b=0),
    font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),
    yaxis=dict(autorange='reversed'),
  )
  return fig


def create_single_owner_breakdown_internal(df):
  """
    Stacked bar: single-owner projects by owner category, coloured by owner type.
    Wrapped owner-type label shown inside each segment when it fits.
    """
  rows = []
  for _, row in df.iterrows():
    owners = row.get('owners') or []
    if len(owners) != 1:
      continue
    o = owners[0]
    rows.append({
      'owner_category': o.get('owner_category') or 'Other',
      'owner_type':     o.get('owner_type') or 'Unknown',
    })

  if not rows:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No single-owner projects for selected filters'))
    return fig

  df_single  = pd.DataFrame(rows)
  counts     = df_single.groupby(['owner_category', 'owner_type']).size().reset_index(name='count')
  cat_order  = (
    counts.groupby('owner_category')['count'].sum()
      .sort_values(ascending=False).index.tolist()
  )
  owner_type_colors = get_owner_type_colors_categorical(_owner_type_category_pairs(df_single))

  fig = px.bar(
    counts, x='owner_category', y='count', color='owner_type', barmode='stack',
    labels={'owner_category': '', 'count': 'Projects', 'owner_type': 'Owner type'},
    category_orders={'owner_category': cat_order},
    color_discrete_map=owner_type_colors,
  )

  # Add wrapped owner-type label inside each segment; constraintext hides it
  # automatically if the segment is too narrow to fit
  for trace in fig.data:
    wrapped = wrap_text(trace.name, width=14)
    trace.update(
      text=[wrapped if (v or 0) > 0 else '' for v in (trace.y or [])],
      textposition='inside',
      insidetextanchor='middle',
      constraintext='inside',
      textfont=dict(size=9, family=FONT_FAMILY, color='white'),
    )

  fig.update_layout(
    title=dict(text=f'Single-owner projects by owner type ({len(df_single)} projects)'),
    showlegend=False,
    margin=dict(l=0, r=0, t=50, b=0),
  )
  return fig

def create_multi_owner_semicircles_internal(df):
  # Derive category colours from config, matching the original CAT_COLORS approach
  CAT_COLORS = {cat: scheme['base'] for cat, scheme in CATEGORY_COLOUR_SCHEME.items()}
  # Fallback for any category not in the scheme
  CAT_COLORS.setdefault('Other', '#808080')

  projects = []
  for _, row in df.iterrows():
    owners = row.get('owners') or []
    owners_valid = [
      o for o in owners
      if (o.get('owner_percent') or 0) > 0
      and o.get('owner_category') in CAT_COLORS
    ]
    if len(owners_valid) < 2:
      continue
    values = [o['owner_percent'] for o in owners_valid]
    if sum(values) <= 90:
      continue
    projects.append({
      'labels': [o['owner_category']          for o in owners_valid],
      'values': values,
      'types':  [o.get('owner_type') or 'Unknown' for o in owners_valid],
    })

  n = len(projects)
  if n == 0:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No multi-owner projects for selected filters'))
    return fig

  cols   = 2
  rows_n = math.ceil(n / cols)
  fig = make_subplots(
    rows=rows_n, cols=cols,
    specs=[[{'type': 'domain'}] * cols for _ in range(rows_n)],
    subplot_titles=[f'Project {i + 1}' for i in range(n)],
    vertical_spacing=0.06, horizontal_spacing=0.02,
  )

  cats_used = set()
  for i, p in enumerate(projects):
    r, c  = i // cols + 1, i % cols + 1
    total = sum(p['values'])
    cats_used.update(p['labels'])

    labels      = p['labels'] + ['']
    vals        = p['values'] + [total]
    text_labels = [f'{v / total * 100:.0f}%' for v in p['values']] + ['']
    hovertypes  = p['types'] + ['']
    colors      = [CAT_COLORS[cat] for cat in p['labels']] + ['rgba(0,0,0,0)']

    fig.add_trace(go.Pie(
      labels=labels, values=vals,
      marker=dict(colors=colors),
      hole=0.5, rotation=270, direction='clockwise', sort=False,
      showlegend=False,
      customdata=hovertypes,
      text=text_labels, textinfo='text', textposition='inside',
      hovertemplate='<b>%{label}</b><br>%{customdata}<br>%{value}%<extra></extra>',
    ), row=r, col=c)

    # Legend — one scatter per category actually used
  for cat, color in CAT_COLORS.items():
    if cat in cats_used:
      fig.add_trace(go.Scatter(
        x=[None], y=[None], mode='markers',
        marker=dict(size=11, color=color),
        name=cat, showlegend=True,
      ))

  fig.update_layout(
    title=f'Ownership breakdown — multi-owner projects (n={n})',
    height=250 * rows_n,
    margin=dict(t=70, b=10, l=0, r=0),
    paper_bgcolor='white',
    plot_bgcolor='rgba(0,0,0,0)',
    xaxis=dict(visible=False),
    yaxis=dict(visible=False),
    font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),
  )
  fig.update_annotations(font_size=12)
  return fig

# ==================== EXPORT CALLABLE ====================

@anvil.server.callable
def export_ownership_chart(chart_key, img_b64, active_filters, chart_title=''):
  return export_figure_from_bytes(
    img_b64, active_filters,
    filename=f'{chart_key}_export.png',
    chart_title=chart_title,
  )