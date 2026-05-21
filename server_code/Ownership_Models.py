"""
Ownership.py — Server module for the Ownership page
====================================================
Structure:
  1. Imports
  2. Utility functions
  3. Data filtering
  4. Data processing
  5. Main callable             — get_all_ownership_charts()
  6. Chart creation functions  — one per chart
  7. Export callable

Charts and what each calculates
--------------------------------
ownership_treemap     : Dollar value of ownership by type — (owner % × project cost),
                        summed across all projects. Shows total ownership value, not
                        number of projects.

scale_pies            : Same dollar-value calculation broken down by project scale.
                        Each slice = (owner % × project cost) summed per owner type
                        within that scale bucket.

indigenous_pie        : Count of survey responses at each level of Indigenous ownership.
                        One response per project or portfolio; a portfolio counts once.

lollipop_chart        : Count of survey responses reporting each ownership-related
                        challenge. One response per project or portfolio.

bubble_chart          : Ownership value × direct financing source. Bubble size =
                        sum of (owner % × project cost) for projects where that owner
                        category used that source. Direct capital sources only.

heatmap               : Same ownership-value calculation as the bubble chart, shown
                        as a colour grid. Darker = higher total ownership value.
                        Direct capital sources only.

all_financing_heatmap : Count of survey responses where that owner category and
                        financing mechanism appear together. Includes ALL mechanism
                        types. Counted by response — a portfolio counts once.
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


def _subtitle(fig, text):
  """
  Add a small grey subtitle annotation just below the plot area top edge.
  Set margin.t to at least 75 on any chart that uses this.
  """
  fig.add_annotation(
    text=text,
    xref='paper', yref='paper',
    x=0, y=1.0,
    xanchor='left', yanchor='top',
    showarrow=False,
    font=dict(family=FONT_FAMILY, size=10, color='#888888'),
  )


# ==================== DATA FILTERING ====================

def apply_filters(df, provinces=None, proj_types=None, stages=None,
                  indigenous_ownership=None, project_scale=None):
  if df.empty:
    return df
  df = df.copy()
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
    df = df[df['project_scale'].isin(project_scale)]
  return df


# ==================== DATA PROCESSING ====================

def process_owners_data(df):
  rows = []
  for _, row in df.iterrows():
    owners = row.get('owners') or []
    for owner in owners:
      rows.append({
        'record_id':            row.get('record_id'),
        'owner_name':           owner.get('owner_name'),
        'owner_type':           owner.get('owner_type'),
        'owner_category':       owner.get('owner_category') or 'Other',
        'owner_percent':        owner.get('owner_percent'),
        'project_type':         row.get('project_type'),
        'project_name':         row.get('project_name'),
        'province':             row.get('province'),
        'project_scale':        row.get('project_scale'),
        'stage':                row.get('stage'),
        'indigenous_ownership': row.get('indigenous_ownership'),
        'total_cost':           row.get('total_cost'),
      })
  return pd.DataFrame(rows)




# ==================== MAIN CALLABLE ====================

@anvil.server.callable
def get_all_ownership_charts(provinces=None, proj_types=None, stages=None,
                             indigenous_ownership=None, project_scale=None):
  df_raw    = get_data()
  df_owners = process_owners_data(df_raw)

  df_raw_filtered    = apply_filters(df_raw,    provinces, proj_types, stages, indigenous_ownership, project_scale)
  df_owners_filtered = apply_filters(df_owners, provinces, proj_types, stages, indigenous_ownership, project_scale)

  if df_owners_filtered.empty:
    empty_fig = go.Figure()
    empty_fig.update_layout(title=dict(text='No data available for selected filters'))
    return {k: empty_fig for k in [
      'ownership_treemap', 'scale_pies', 'indigenous_pie',
      'lollipop_chart', 'bubble_chart', 'heatmap', 'all_financing_heatmap',
    ]}

  return {
    'ownership_treemap':     apply_display_template(create_ownership_treemap_internal(df_owners_filtered)),
    'scale_pies':            apply_display_template(create_ownership_scale_pies_internal(df_owners_filtered)),
    'indigenous_pie':        apply_display_template(create_indigenous_ownership_stacked_internal(df_owners_filtered)),
    'lollipop_chart':        apply_display_template(create_bottleneck_lollipop_internal(df_raw_filtered)),
    'bubble_chart':          apply_display_template(create_ownership_financing_bubble_internal(df_raw_filtered)),
    'all_financing_heatmap': apply_display_template(create_ownership_all_financing_heatmap_internal(df_raw_filtered)),
  }


# ==================== CHART CREATION ====================

def create_ownership_treemap_internal(df_owners):
  """
  WHAT IT CALCULATES:
  For every owner type, sums (ownership stake % ÷ 100 × total project cost)
  across every project that owner type appears in. The result is the total
  dollar value that owner type collectively holds across the dataset. Tile
  size and the % label both reflect this dollar value as a share of the grand
  total — not a count of projects or responses.
  """
  df_val = df_owners.copy()
  df_val['ownership_value'] = (df_val['owner_percent'] / 100) * df_val['total_cost']
  value_data = df_val.groupby(['owner_type', 'owner_category'], as_index=False)['ownership_value'].sum()
  value_data['value'] = value_data['ownership_value']

  owner_colors = get_owner_type_colors_categorical(_owner_type_category_pairs(df_owners))
  cat_totals   = value_data.groupby('owner_category')['value'].sum()
  labels, parents, values, colors_list = [], [], [], []

  for cat, total in cat_totals.items():
    scheme = CATEGORY_COLOUR_SCHEME.get(cat, CATEGORY_COLOUR_SCHEME['Other'])
    labels.append(cat); parents.append(''); values.append(total)
    colors_list.append(scheme['base'])

  for _, row in value_data.iterrows():
    labels.append(wrap_text(row['owner_type'], width=20))
    parents.append(row['owner_category']); values.append(row['value'])
    colors_list.append(owner_colors.get(row['owner_type'], '#808080'))

  fig = go.Figure(go.Treemap(
    labels=labels, parents=parents, values=values,
    branchvalues='total',
    texttemplate='<b>%{label}</b><br>%{percentRoot:.1%}',
    hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<extra></extra>',
    marker=dict(colors=colors_list, line=dict(width=2, color='white')),
  ))
  fig.update_layout(
    title=dict(text='Ownership composition of community energy projects'),
    margin=dict(t=75, b=0, l=0, r=0),
  )
  _subtitle(fig,
            'Tile size = sum of (ownership % × project cost) for each owner type across all projects — '
            'shows total dollar value of ownership, not number of projects')
  return fig


def create_ownership_scale_pies_internal(df_owners):
  """
  WHAT IT CALCULATES:
  For each project scale bucket, sums (ownership % ÷ 100 × total project cost)
  per owner type. Slice size reflects the total dollar value of that owner type's
  combined stake in projects of that scale — not how many projects it appears in.
  """
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
  cats_present = [c for c in CATEGORY_ORDER_OWNERS if c in df_owners['owner_category'].unique()]
  fig    = go.Figure()
  n_pies = len(scales)

  for i, scale in enumerate(scales):
    sub   = df_owners[df_owners['project_scale'] == scale]
    n     = sub['record_id'].nunique()
    sub_val = sub.copy()
    sub_val['ownership_value'] = (sub_val['owner_percent'] / 100) * sub_val['total_cost']
    value_grouped = sub_val.groupby(['owner_type', 'owner_category'], as_index=False)['ownership_value'].sum()
    value_grouped['cat_order'] = value_grouped['owner_category'].apply(
      lambda c: CATEGORY_ORDER_OWNERS.index(c) if c in CATEGORY_ORDER_OWNERS else 999)
    value_grouped.sort_values(['cat_order', 'owner_type'], inplace=True)
    value_grouped.reset_index(drop=True, inplace=True)
    value_grouped['pct'] = (value_grouped['ownership_value'] / value_grouped['ownership_value'].sum()) * 100
    value_grouped['text_display'] = value_grouped['pct'].apply(lambda x: f'{x:.1f}%' if x >= 5 else '')

    pad     = 0.01
    x_start = i / n_pies + pad
    x_end   = (i + 1) / n_pies - pad
    domain  = dict(x=[x_start, x_end], y=[0.25, 1.0])
    title_style = dict(
      text=f"{scale}<br>({n} projects)",
      font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),
      position='top center',
    )
    fig.add_trace(go.Pie(
      labels=value_grouped['owner_type'], values=value_grouped['ownership_value'],
      domain=domain, title=title_style,
      marker=dict(colors=[owner_type_colors[ot] for ot in value_grouped['owner_type']]),
      sort=False, direction='clockwise',
      textinfo='text', text=value_grouped['text_display'],
      hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<br>%{percent} of value<extra></extra>',
      showlegend=False, visible=True,
    ))

  shades_per_category = {}
  for cat in cats_present:
    types_in_cat = sorted(df_owners[df_owners['owner_category'] == cat]['owner_type'].unique())
    shades_per_category[cat] = [owner_type_colors[ot] for ot in types_in_cat if ot in owner_type_colors]

  shapes, annotations = [], []
  swatch_width = 0.04; swatch_height = 0.025
  label_padding = 0.006; entry_padding = 0.025; char_width_est = 0.0085

  def entry_width(cat):
    return swatch_width + label_padding + len(cat) * char_width_est

  active_cats = [c for c in cats_present if shades_per_category[c]]
  total_width = sum(entry_width(c) for c in active_cats) + entry_padding * max(0, len(active_cats) - 1)
  current_x   = (1 - total_width) / 2
  y_center    = 0.20
  y_swatch_bot = y_center - swatch_height / 2
  y_swatch_top = y_center + swatch_height / 2

  for cat in active_cats:
    shades    = shades_per_category[cat]
    seg_width = swatch_width / len(shades)
    for k, shade in enumerate(shades):
      shapes.append(dict(type='rect', xref='paper', yref='paper',
                         x0=current_x + k * seg_width, x1=current_x + (k + 1) * seg_width,
                         y0=y_swatch_bot, y1=y_swatch_top, fillcolor=shade, line=dict(width=0)))
    shapes.append(dict(type='rect', xref='paper', yref='paper',
                       x0=current_x, x1=current_x + swatch_width,
                       y0=y_swatch_bot, y1=y_swatch_top,
                       fillcolor='rgba(0,0,0,0)', line=dict(color='lightgray', width=0.5)))
    annotations.append(dict(xref='paper', yref='paper',
                            x=current_x + swatch_width + label_padding, y=y_center,
                            xanchor='left', yanchor='middle', text=cat, showarrow=False,
                            font=dict(family=FONT_FAMILY, size=11, color=FONT_COLOR)))
    current_x += entry_width(cat) + entry_padding

  fig.update_layout(
    title=dict(text='Ownership composition by project scale'),
    showlegend=False, shapes=shapes, annotations=annotations,
    margin=dict(t=75, b=0, l=0, r=0),
  )
  _subtitle(fig,
            'Slice size = sum of (ownership % × project cost) per owner type at each scale — '
            'reflects dollar value of ownership stake, not number of projects')
  return fig


def create_indigenous_ownership_stacked_internal(df_owners):
  """
  WHAT IT CALCULATES:
  Counts how many distinct survey responses fall into each level of Indigenous
  ownership. One response represents one project or portfolio — a portfolio
  response covering multiple projects still counts as one. The % shown is each
  level's share of the total response count.
  """
  ownership_counts = df_owners.groupby('indigenous_ownership')['record_id'].nunique().reset_index()
  ownership_counts.columns = ['Category', 'Count']
  total = ownership_counts['Count'].sum()
  ownership_counts['Percentage'] = (ownership_counts['Count'] / total) * 100
  order = [
    'Not sure', 'No Indigenous ownership',
    'Minority Indigenous owned (1-49%)', 'Half Indigenous owned (50%)',
    'Majority Indigenous owned (51-99%)', 'Wholly Indigenous owned (100%)',
  ]
  ownership_counts['Category'] = pd.Categorical(ownership_counts['Category'], categories=order, ordered=True)
  ownership_counts = ownership_counts.sort_values('Category').reset_index(drop=True)
  colors = [gradient_palette[i * 2] for i in range(len(ownership_counts))][::-1]

  fig = go.Figure()
  for i, row in ownership_counts.iterrows():
    fig.add_trace(go.Bar(
      x=[''], y=[row['Count']], name=row['Category'], orientation='v',
      text=f"<b>{row['Percentage']:.1f}%  -  {row['Category']}</b>",
      textposition='inside', marker=dict(color=colors[i]),
      hovertemplate=f"<b>{row['Category']}</b><br>Responses: {row['Count']}<br>{row['Percentage']:.1f}%<extra></extra>",
    ))
  fig.update_layout(
    title=dict(text='Indigenous project ownership'),
    barmode='stack', showlegend=False,
    xaxis=dict(visible=False), yaxis=dict(visible=False),
    margin=dict(t=75, b=0, l=0, r=0),
  )
  _subtitle(fig,
            'Count of survey responses at each level of Indigenous ownership — '
            'counted by response, not individual projects (a portfolio counts once)')
  return fig


def create_bottleneck_lollipop_internal(df):
  """
  WHAT IT CALCULATES:
  Counts how many distinct survey responses reported experiencing each
  ownership-related challenge. One response per project or portfolio —
  a portfolio covering multiple projects counts as one response.
  """
  KEEP = [
    'Challenges with project governance or decision-making',
    'Conflicts among stakeholders or partners',
    'Limited community engagement or support',
  ]
  counts_df = (df['bottlenecks'].explode().value_counts()
    .reset_index().rename(columns={'index': 'bottleneck', 'bottlenecks': 'count'}))
  counts_df.columns = ['bottleneck', 'count']
  counts_df = counts_df[counts_df['bottleneck'].isin(KEEP)].sort_values('count', ascending=True)

  bottlenecks = counts_df['bottleneck'].tolist()
  counts      = counts_df['count'].tolist()
  y_pos       = list(range(len(bottlenecks)))
  color       = dunsparce_colors[11]
  fig         = make_subplots()

  for i, (label, count) in enumerate(zip(bottlenecks, counts)):
    fig.add_scatter(x=[0, count], y=[i, i], mode='lines',
                    line=dict(color=color, width=6), showlegend=False, hoverinfo='skip')
    fig.add_annotation(text=label, x=0, y=i + 0.37, xanchor='left', yanchor='middle',
                       showarrow=False, font=dict(family=FONT_FAMILY, size=13, color='#392000'))
    fig.add_annotation(text=f'<b>{count}</b>', x=count, y=i,
                       xanchor='center', yanchor='middle', showarrow=False,
                       font=dict(family=FONT_FAMILY, size=16, color='white'))

  fig.add_scatter(x=counts, y=y_pos, mode='markers',
                  marker=dict(size=30, color=color), showlegend=False,
                  hovertemplate='<b>%{text}</b><br>Responses: %{x}<extra></extra>', text=bottlenecks)
  fig.update_xaxes(visible=False, range=[0, max(counts) * 1.15] if counts else [0, 10], showgrid=False)
  fig.update_yaxes(visible=False, showgrid=False)
  fig.update_layout(
    title=dict(text='Ownership bottlenecks'),
    margin=dict(l=0, r=0, t=75, b=0),
  )
  _subtitle(fig,
            'Count of survey responses reporting each challenge — '
            'counted by response, not individual projects (a portfolio counts once)')
  return fig


def _build_ownership_financing_pairs(df, direct_only=True):
  """
  One row per (record_id, owner_category, finance_category) with
  owner_dollar = (combined ownership % for that category / 100) × total_cost.
  direct_only=True  → 'Direct sources of capital' only (for dollar scaling).
  direct_only=False → all financing mechanisms (for response counts).
  """
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
          'record_id':        rid,
          'owner_category':   oc,
          'finance_category': fc,
          'owner_dollar':     (pct_sum / 100) * total_cost,
        })

  if not pairs:
    return pd.DataFrame()
  return pd.DataFrame(pairs)


def create_ownership_financing_bubble_internal(df):
  """
  Bubble chart: owner categories (x) vs direct financing sources (y).
  Bubble size = sum of (ownership % × project cost) across projects where that
  owner category used that source. Direct capital sources only.
  """
  pairs_df = _build_ownership_financing_pairs(df, direct_only=True)
  if pairs_df.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No ownership-financing data available'))
    return fig

  dollar_data = (pairs_df.groupby(['owner_category', 'finance_category'])['owner_dollar']
    .sum().reset_index(name='amount'))
  dollar_data['amount_millions'] = dollar_data['amount'] / 1_000_000

  owner_order   = dollar_data.groupby('owner_category')['amount'].sum().sort_values(ascending=False).index.tolist()
  finance_order = dollar_data.groupby('finance_category')['amount'].sum().sort_values(ascending=False).index.tolist()

  finance_wrap_map = {f: wrap_text(f, width=35) for f in finance_order}
  finance_order_w  = [finance_wrap_map[f] for f in finance_order]
  dollar_data['finance_w'] = dollar_data['finance_category'].map(finance_wrap_map)

  def owner_color(cat):
    scheme = CATEGORY_COLOUR_SCHEME.get(cat, CATEGORY_COLOUR_SCHEME.get('Other', {}))
    return scheme.get('base', '#808080')

  def normalize_size(values, min_size=12, max_size=50):
    if values.max() == values.min(): return [30] * len(values)
    return ((values - values.min()) / (values.max() - values.min()) * (max_size - min_size) + min_size).tolist()

  def format_amount(x):
    if x >= 1000: return f'{x / 1000:.1f}B'
    if x >= 1:    return f'{x:.1f}M'
    return f'{x * 1000:.0f}K'

  fig = go.Figure()
  fig.add_trace(go.Scatter(
    x=dollar_data['owner_category'],
    y=dollar_data['finance_w'],
    mode='markers+text',
    marker=dict(
      size=normalize_size(dollar_data['amount_millions']),
      color=[owner_color(c) for c in dollar_data['owner_category']],
    ),
    text=dollar_data['amount_millions'].apply(format_amount),
    textposition='middle center',
    textfont=dict(size=9, color='white', family=FONT_FAMILY),
    hovertemplate='<b>%{y}</b><br>Owner: %{x}<br>Ownership value: $%{text}<extra></extra>',
  ))
  fig.update_layout(
    title=dict(text='Ownership value by direct financing source', x=0, xanchor='left'),
    margin=dict(l=0, b=0, t=50, r=0),
    font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),
    xaxis=dict(
      title='', tickangle=-20, showgrid=False, linecolor='#e0e0e0',
      categoryorder='array', categoryarray=owner_order,
      range=[-0.5, len(owner_order) - 0.5],
    ),
    yaxis=dict(
      title='', showgrid=True, gridcolor='#f0f0f0', gridwidth=1,
      linecolor='#e0e0e0', categoryorder='array',
      categoryarray=finance_order_w[::-1], range=[-0.8, len(finance_order_w)],
    ),
    showlegend=False,
  )
  return fig


def create_ownership_all_financing_heatmap_internal(df):
  """
  Heatmap: owner categories (x) vs all financing mechanisms (y).
  Cell value = count of survey responses where that owner category and financing
  mechanism co-occur. Counted by response, not individual projects.
  """
  pairs_df = _build_ownership_financing_pairs(df, direct_only=False)
  if pairs_df.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No ownership-financing data available'))
    return fig

  count_data = (pairs_df.groupby(['owner_category', 'finance_category'])['record_id']
    .nunique().reset_index(name='count'))

  owner_order   = count_data.groupby('owner_category')['count'].sum().sort_values(ascending=False).index.tolist()
  finance_order = count_data.groupby('finance_category')['count'].sum().sort_values(ascending=False).index.tolist()
  finance_wrap_map = {f: wrap_text(f, width=35) for f in finance_order}
  finance_order_w  = [finance_wrap_map[f] for f in finance_order]

  count_data['finance_w'] = count_data['finance_category'].map(finance_wrap_map)
  count_pivot = (count_data
    .pivot_table(index='finance_w', columns='owner_category', values='count', fill_value=0)
    .reindex(index=finance_order_w, columns=owner_order, fill_value=0))

  max_val = count_pivot.values.max() or 1
  annotations = []
  for fi, row_label in enumerate(count_pivot.index):
    for oi, col_label in enumerate(count_pivot.columns):
      val = count_pivot.iloc[fi, oi]
      if val <= 0: continue
      annotations.append(dict(
        x=col_label, y=row_label, text=f'<b>{int(val)}</b>',
        showarrow=False, xref='x', yref='y',
        font=dict(family=FONT_FAMILY, size=10,
                  color='white' if val > max_val * 0.5 else FONT_COLOR),
      ))

  fig = go.Figure(go.Heatmap(
    z=count_pivot.values, x=owner_order, y=finance_order_w,
    colorscale=[[0, '#f7f9fc'], [1, dunsparce_colors[1]]],
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


# ==================== EXPORT CALLABLE ====================

@anvil.server.callable
def export_ownership_chart(chart_key, img_b64, active_filters, chart_title=''):
  return export_figure_from_bytes(
    img_b64, active_filters,
    filename=f'{chart_key}_export.png',
    chart_title=chart_title,
  )