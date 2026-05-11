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

Display template is applied centrally in get_all_ownership_charts() via
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
  """Wrap long strings with <br> tags for display inside Plotly visualisations."""
  return '<br>'.join(textwrap.wrap(str(text), width=width))


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


def _owner_type_category_pairs(df_owners):
  """Return unique (owner_type, owner_category) tuples for colour lookup."""
  return list(
    df_owners[['owner_type', 'owner_category']]
      .drop_duplicates()
      .itertuples(index=False, name=None)
  )


# ==================== DATA FILTERING ====================

def apply_filters(df, provinces=None, proj_types=None, stages=None,
                  indigenous_ownership=None, project_scale=None):
  """Apply user-selected filters to a dataframe. Returns a filtered copy."""
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
  """
  Convert a dataframe with an 'owners' list column into long format.
  Each row represents one owner with their type, category, and project context.
  The owner_category field is read directly from the cleaned data.
  """
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
  """
  Single server call returning all ownership chart figures.
  Data is loaded and processed once, shared across all chart builders.
  apply_display_template() is called here on every figure.
  """
  # ── Load and process data once ──
  df_raw    = get_data()
  df_owners = process_owners_data(df_raw)

  # ── Filter both views ──
  df_raw_filtered    = apply_filters(df_raw,    provinces, proj_types, stages, indigenous_ownership, project_scale)
  df_owners_filtered = apply_filters(df_owners, provinces, proj_types, stages, indigenous_ownership, project_scale)

  # ── Guard: empty result ──
  if df_owners_filtered.empty:
    empty_fig = go.Figure()
    empty_fig.update_layout(title=dict(text='No data available for selected filters'))
    return {k: empty_fig for k in [
      'ownership_treemap', 'scale_pies', 'indigenous_pie',
      'lollipop_chart', 'funnel_chart',
    ]}

  # ── Build all charts with display template applied centrally ──
  return {
    'ownership_treemap': apply_display_template(create_ownership_treemap_internal(df_owners_filtered)),
    'scale_pies':        apply_display_template(create_ownership_scale_pies_internal(df_owners_filtered)),
    'indigenous_pie':    apply_display_template(create_indigenous_ownership_stacked_internal(df_owners_filtered)),
    'lollipop_chart':    apply_display_template(create_bottleneck_lollipop_internal(df_raw_filtered)),
    'funnel_chart':      apply_display_template(create_ownership_financing_funnel_internal(df_raw_filtered)),
  }


# ==================== CHART CREATION ====================
# Each function sets only chart-specific properties.
# Generic styling is handled by apply_display_template() above.

def create_ownership_treemap_internal(df_owners):
  """
  Hierarchical treemap with owner-type categories as parent nodes.
  Categories form the outer boxes (coloured with the base hue); owner types
  sit inside, coloured with shades of the parent. Toggle between dollar
  value and project count.
  """
  # ── Aggregate for both views ──
  project_data = df_owners.groupby(['owner_type', 'owner_category'], as_index=False)['owner_percent'].sum()
  project_data['value'] = project_data['owner_percent']

  df_val = df_owners.copy()
  df_val['ownership_value'] = (df_val['owner_percent'] / 100) * df_val['total_cost']
  value_data = df_val.groupby(['owner_type', 'owner_category'], as_index=False)['ownership_value'].sum()
  value_data['value'] = value_data['ownership_value']

  owner_colors = get_owner_type_colors_categorical(_owner_type_category_pairs(df_owners))

  def make_treemap(data, visible=True):
    cat_totals = data.groupby('owner_category')['value'].sum()
    labels, parents, values, colors_list = [], [], [], []

    # Category-level (parent) nodes — base hue
    for cat, total in cat_totals.items():
      scheme = CATEGORY_COLOUR_SCHEME.get(cat, CATEGORY_COLOUR_SCHEME['Other'])
      labels.append(cat)
      parents.append('')
      values.append(total)
      colors_list.append(scheme['base'])

    # Owner-type (child) nodes — shaded
    for _, row in data.iterrows():
      labels.append(wrap_text(row['owner_type'], width=20))
      parents.append(row['owner_category'])
      values.append(row['value'])
      colors_list.append(owner_colors.get(row['owner_type'], '#808080'))

    return go.Treemap(
      labels=labels, parents=parents, values=values,
      branchvalues='total',
      textinfo='label+percent parent',
      hovertemplate='<b>%{label}</b><br>%{value:,.0f}<extra></extra>',
      visible=visible,
      marker=dict(colors=colors_list, line=dict(width=2, color='white')),
    )

  fig = go.Figure()
  fig.add_trace(make_treemap(value_data,   visible=True))
  fig.add_trace(make_treemap(project_data, visible=False))

  fig.update_layout(
    title=dict(text='Ownership composition of community energy projects'),
    updatemenus=[dict(
      type='buttons', direction='left',
      buttons=[
        dict(label='By Dollar Amount', method='update', args=[{'visible': [True, False]}]),
        dict(label='By Project Count', method='update', args=[{'visible': [False, True]}]),
      ],
      pad={'r': 10, 't': 10}, showactive=True,
      x=0.5, y=1.07, xanchor='left', yanchor='top',
      bgcolor='rgba(255,255,255,0.8)', bordercolor='gray', borderwidth=1,
    )],
    margin=dict(t=0, b=0, l=0, r=0),
  )
  return fig


def create_ownership_scale_pies_internal(df_owners):
  """
  Pie charts of ownership composition for each project scale.
  Owner types from the same category sit adjacent in each pie
  (sorted by CATEGORY_ORDER_OWNERS, then alphabetically within).
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

  fig = make_subplots(
    rows=1, cols=len(scales),
    specs=[[{'type': 'domain'}] * len(scales)],
  )

  for i, scale in enumerate(scales):
    sub     = df_owners[df_owners['project_scale'] == scale]
    grouped = sub.groupby(['owner_type', 'owner_category'], as_index=False)['owner_percent'].sum()
    n       = sub['record_id'].nunique()

    # ── Sort so category groups stay adjacent ──
    grouped['cat_order'] = grouped['owner_category'].apply(
      lambda c: CATEGORY_ORDER_OWNERS.index(c) if c in CATEGORY_ORDER_OWNERS else 999
    )
    grouped = grouped.sort_values(['cat_order', 'owner_type']).reset_index(drop=True)

    total = grouped['owner_percent'].sum()
    grouped['percentage']   = (grouped['owner_percent'] / total) * 100
    grouped['text_display'] = grouped['percentage'].apply(
      lambda x: f'{x:.1f}%' if x >= 5 else ''
    )

    fig.add_trace(
      go.Pie(
        labels=grouped['owner_type'],
        values=grouped['owner_percent'],
        title=dict(
          text=f"{scale}<br>({n} projects)",
          font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),
          position='top center',
        ),
        marker=dict(colors=[owner_type_colors[ot] for ot in grouped['owner_type']]),
        sort=False,
        direction='clockwise',
        textinfo='text',
        text=grouped['text_display'],
        hovertemplate='<b>%{label}</b><br>%{percent}<extra></extra>',
      ),
      row=1, col=i + 1,
    )

  fig.update_layout(
    title=dict(text='Ownership composition by project scale'),
    showlegend=False,
    margin=dict(t=0, b=0, l=0, r=0),
  )
  return fig


def create_indigenous_ownership_stacked_internal(df_owners):
  """
  Single stacked bar showing distribution of Indigenous ownership level
  across projects. Uses every-second gradient palette colour (reversed).
  """
  ownership_counts = df_owners.groupby('indigenous_ownership')['record_id'].nunique().reset_index()
  ownership_counts.columns = ['Category', 'Count']
  total = ownership_counts['Count'].sum()
  ownership_counts['Percentage'] = (ownership_counts['Count'] / total) * 100

  order = [
    'Not sure',
    'No Indigenous ownership',
    'Minority Indigenous owned (1-49%)',
    'Half Indigenous owned (50%)',
    'Majority Indigenous owned (51-99%)',
    'Wholly Indigenous owned (100%)',
  ]
  ownership_counts['Category'] = pd.Categorical(ownership_counts['Category'], categories=order, ordered=True)
  ownership_counts = ownership_counts.sort_values('Category').reset_index(drop=True)

  colors = [gradient_palette[i * 2] for i in range(len(ownership_counts))][::-1]

  fig = go.Figure()
  for i, row in ownership_counts.iterrows():
    fig.add_trace(go.Bar(
      x=[''], y=[row['Count']],
      name=row['Category'],
      orientation='v',
      text=f"<b>{row['Percentage']:.1f}%  -  {row['Category']}</b>",
      textposition='inside',
      marker=dict(color=colors[i]),
      hovertemplate=f"<b>{row['Category']}</b><br>Projects: {row['Count']}<br>{row['Percentage']:.1f}%<extra></extra>",
    ))

  fig.update_layout(
    title=dict(text='Indigenous project ownership'),
    barmode='stack',
    showlegend=False,
    xaxis=dict(visible=False),
    yaxis=dict(visible=False),
    margin=dict(t=40, b=0, l=0, r=0),
  )
  return fig


def create_bottleneck_lollipop_internal(df):
  """
  Lollipop chart of ownership-related bottlenecks.
  Pre-selected key bottlenecks only. Single colour from dunsparce palette.
  """
  KEEP = [
    'Challenges with project governance or decision-making',
    'Conflicts among stakeholders or partners',
    'Limited community engagement or support',
  ]

  counts_df = (df['bottlenecks'].explode().value_counts()
    .reset_index()
    .rename(columns={'index': 'bottleneck', 'bottlenecks': 'count'}))
  counts_df.columns = ['bottleneck', 'count']
  counts_df = (counts_df[counts_df['bottleneck'].isin(KEEP)]
    .sort_values('count', ascending=True))

  bottlenecks = counts_df['bottleneck'].tolist()
  counts      = counts_df['count'].tolist()
  y_pos       = list(range(len(bottlenecks)))
  color       = dunsparce_colors[11]

  fig = make_subplots()

  for i, (label, count) in enumerate(zip(bottlenecks, counts)):
    fig.add_scatter(
      x=[0, count], y=[i, i], mode='lines',
      line=dict(color=color, width=6), showlegend=False, hoverinfo='skip',
    )
    fig.add_annotation(
      text=label, x=0, y=i + 0.37, xanchor='left', yanchor='middle',
      showarrow=False,
      font=dict(family=FONT_FAMILY, size=13, color='#392000'),
    )
    fig.add_annotation(
      text=f'<b>{count}</b>', x=count, y=i, xanchor='center', yanchor='middle',
      showarrow=False,
      font=dict(family=FONT_FAMILY, size=16, color='white'),
    )

  fig.add_scatter(
    x=counts, y=y_pos, mode='markers',
    marker=dict(size=30, color=color), showlegend=False,
    hovertemplate='<b>%{text}</b><br>Count: %{x}<extra></extra>',
    text=bottlenecks,
  )

  fig.update_xaxes(visible=False, range=[0, max(counts) * 1.15] if counts else [0, 10], showgrid=False)
  fig.update_yaxes(visible=False, showgrid=False)
  fig.update_layout(
    margin=dict(l=0, r=0, t=35, b=0),
    title=dict(text='Ownership bottlenecks'),
  )
  return fig


def create_ownership_financing_funnel_internal(df):
  """
  Funnel chart of top 10 (owner type -> financing category) combinations.
  Coloured by rank using the gradient palette.
  """
  pairs = []
  for _, row in df.iterrows():
    owners    = row.get('owners') or []
    financing = row.get('financing_mech') or []
    if not owners or not financing:
      continue
    for o in owners:
      for f in financing:
        pairs.append({
          'Owner':   o.get('owner_type', 'Unknown'),
          'Finance': f.get('category', 'Unknown'),
        })

  if not pairs:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No ownership-financing data available'))
    return fig

  pairs_df = pd.DataFrame(pairs)
  combo_counts = (pairs_df.groupby(['Owner', 'Finance'])
    .size().reset_index(name='Count'))
  combo_counts['Label'] = combo_counts['Owner'] + ' -> ' + combo_counts['Finance']
  combo_counts = combo_counts.sort_values('Count', ascending=False).head(10).reset_index(drop=True)

  combo_counts['Label_wrapped'] = combo_counts['Label'].apply(lambda x: wrap_text(x, width=50))

  fig = go.Figure(go.Funnel(
    y=combo_counts['Label_wrapped'],
    x=combo_counts['Count'],
    textposition='inside',
    marker=dict(color=gradient_palette[:len(combo_counts)], line=dict(width=0)),
    customdata=combo_counts['Label'],
    hovertemplate='<b>%{customdata}</b><br>Count: %{x}<extra></extra>',
  ))

  fig.update_layout(
    title=dict(text='Top 10 ownership-financing combinations'),
    yaxis=dict(side='left'),
    margin=dict(t=50, b=30, l=20, r=30),
  )
  return fig


# ==================== EXPORT CALLABLE ====================

@anvil.server.callable
def export_ownership_chart(chart_key, img_b64, active_filters, chart_title=''):
  return export_figure_from_bytes(
    img_b64,
    active_filters,
    filename=f'{chart_key}_export.png',
    chart_title=chart_title,
  )