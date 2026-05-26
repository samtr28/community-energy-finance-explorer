"""
Outcomes_Explorer.py — Server module for the Outcomes & Impacts page
====================================================================
Structure:
  1. Imports
  2. Data filtering            — apply_filters()
  3. Main callable             — get_all_outcomes_charts()
  4. Chart creation functions  — one per chart type
  5. Export callable           — export_outcomes_chart()

Display template is applied centrally in get_all_outcomes_charts() via
apply_display_template() from Export_Utils. Individual chart functions
only set chart-specific properties (title text, axis specifics, and any
explicit fonts that must survive the template).
"""

import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import (
gradient_palette, dunsparce_colors,
FONT_FAMILY, FONT_SIZE, FONT_COLOR,
)
from .Global_Server_Functions import get_data
from .Export_Utils import export_figure_from_bytes, apply_display_template


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
  if proj_types:           df = df[df['project_type'].apply(lambda x: any(t in x for t in proj_types) if isinstance(x, list) else False)]
  if stages:               df = df[df['stage'].isin(stages)]
  if indigenous_ownership: df = df[df['indigenous_ownership'].isin(indigenous_ownership)]
  if project_scale:        df = df[df['project_scale'].isin(project_scale)]
  return df


# ==================== MAIN CALLABLE ====================

@anvil.server.callable
def get_all_outcomes_charts(provinces=None, proj_types=None, stages=None,
                            indigenous_ownership=None, project_scale=None):
  """
  Single server call returning all outcomes/impacts chart figures.
  apply_display_template() is called here on every figure — chart functions
  only need to set chart-specific properties.

  Returns a dict with keys:
    indigenous_agreements, jobs_chart, ghg_methodology,
    ghg_timeline, key_objectives
  """
  df          = get_data()
  df_filtered = apply_filters(df, provinces, proj_types, stages,
                              indigenous_ownership, project_scale)

  # ── Guard: return empty figures if nothing matches ──
  if df_filtered.empty:
    empty_fig = go.Figure()
    empty_fig.update_layout(title=dict(text='No data available for selected filters'))
    return {k: empty_fig for k in [
      'indigenous_agreements', 'jobs_chart', 'ghg_methodology',
      'ghg_timeline', 'key_objectives',
    ]}

  # ── Build all charts and apply the display template to each ──
  return {
    'indigenous_agreements': apply_display_template(create_indigenous_agreements_chart(df_filtered)),
    'jobs_chart':            apply_display_template(create_jobs_chart(df_filtered)),
    'ghg_methodology':       apply_display_template(create_ghg_methodology_chart(df_filtered)),
    'ghg_timeline':          apply_display_template(create_ghg_charts(df_filtered)),
    'key_objectives':        apply_display_template(create_key_objectives_bar_chart(df_filtered)),
  }


# ==================== CHART CREATION ====================
# Each function sets only chart-specific properties.
# Generic styling (backgrounds, fonts, title size, margins) is handled
# by apply_display_template() in get_all_outcomes_charts() above.
# Title text is still set here since it is chart-specific content.

def create_indigenous_agreements_chart(df):
  """Donut chart: distribution of indigenous agreement types."""
  agreements_list = []
  for agreement in df['indigenous_agreements']:
    if isinstance(agreement, list):
      agreements_list.extend(agreement)

  if not agreements_list:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No indigenous agreements data'))
    return fig

  agreements_counts = pd.Series(agreements_list).value_counts()
  fig = go.Figure(data=[go.Pie(
    labels=agreements_counts.index,
    values=agreements_counts.values,
    hole=0.4,
    showlegend=True,
    marker=dict(colors=dunsparce_colors[:len(agreements_counts)])
  )])
  fig.update_layout(
    title=dict(text='Project Agreements with Indigenous Communities'),
    margin=dict(t=50, b=0, l=0, r=0),
    legend=dict(orientation='v'),
  )
  return fig


def create_jobs_chart(df):
  """Grouped bar chart: full-time vs part-time jobs by project phase."""
  jobs_list = []
  for job_entries in df['jobs']:
    if isinstance(job_entries, list):
      jobs_list.extend(job_entries)

  if not jobs_list:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No jobs data'))
    return fig

  jobs_df = pd.DataFrame(jobs_list)
  grouped = jobs_df.groupby('phase')[['full_time', 'part_time']].sum().fillna(0)
  reporting_counts = jobs_df.groupby('phase').agg({
    'full_time': lambda x: x.notna().sum(),
    'part_time': lambda x: x.notna().sum()
  })
  total_projects = len(df)

  fig = go.Figure(data=[
    go.Bar(name='Full-time', x=grouped.index, y=grouped['full_time'], marker_color=dunsparce_colors[0]),
    go.Bar(name='Part-time', x=grouped.index, y=grouped['part_time'], marker_color=dunsparce_colors[1])
  ])

  bar_width = 0.4
  for i, phase in enumerate(grouped.index):
    # Explicit grey font — preserved through apply_display_template
    fig.add_annotation(
      x=i - bar_width / 2, y=grouped.loc[phase, 'full_time'],
      text=f"{reporting_counts.loc[phase, 'full_time']} projects<br>{grouped.loc[phase, 'full_time']:.0f} jobs",
      showarrow=False, yshift=20,
      font=dict(family=FONT_FAMILY, size=12, color='gray'),
    )
    fig.add_annotation(
      x=i + bar_width / 2, y=grouped.loc[phase, 'part_time'],
      text=f"{reporting_counts.loc[phase, 'part_time']} projects<br>{grouped.loc[phase, 'part_time']:.0f} jobs",
      showarrow=False, yshift=20,
      font=dict(family=FONT_FAMILY, size=12, color='gray'),
    )

  fig.update_layout(
    barmode='group',
    title=dict(text=f'Jobs by Phase: Full-time vs Part-time (Total Projects: {total_projects})'),
    xaxis_title='', yaxis_title='',
    showlegend=True,
    legend=dict(orientation='h', yanchor='top', y=-0.1, xanchor='center', x=0.5),
    margin=dict(t=50, b=0, l=0, r=0),
  )
  return fig


def create_ghg_methodology_chart(df):
  """Two treemaps: GHG reduction tools used, and who calculated the reductions."""
  tools_list = []
  for tool_entries in df['ghg_tools']:
    if isinstance(tool_entries, list):
      tools_list.extend(tool_entries)

  who_counts = df['ghg_who'].value_counts()

  if not tools_list and who_counts.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No GHG methodology data'))
    return fig

  tools_counts = pd.Series(tools_list).value_counts() if tools_list else pd.Series(dtype=int)

  fig = make_subplots(
    rows=1, cols=2,
    specs=[[{'type': 'treemap'}, {'type': 'treemap'}]],
    subplot_titles=('GHG Reduction Tools', 'Who Calculated GHG Reductions'),
    horizontal_spacing=0.02
  )

  if not tools_counts.empty:
    tools_colors = [gradient_palette[i % len(gradient_palette)] for i in range(len(tools_counts))]
    fig.add_trace(
      go.Treemap(
        labels=tools_counts.index, parents=[''] * len(tools_counts),
        values=tools_counts.values, textinfo='label+value',
        marker=dict(colors=tools_colors, line=dict(width=2, color='white'))
      ),
      row=1, col=1
    )

  if not who_counts.empty:
    who_colors = [gradient_palette[i % len(gradient_palette)] for i in range(len(who_counts))]
    fig.add_trace(
      go.Treemap(
        labels=who_counts.index, parents=[''] * len(who_counts),
        values=who_counts.values, textinfo='label+value',
        marker=dict(colors=who_colors, line=dict(width=2, color='white'))
      ),
      row=1, col=2
    )

  fig.update_layout(
    title=dict(text='GHG Reduction Methodology'),
    height=500,
    margin=dict(t=50, b=0, l=0, r=0),
  )
  return fig


def create_ghg_charts(df):
  """
  Two stacked subplots:
    1. Year-by-year reduction capacity added each year (bar chart, megatonnes CO2e)
    2. Cumulative lifetime reductions through 2050 (filled area, megatonnes CO2e)

  NOTE: ghg_reduction is assumed to be stored in tonnes CO2e and is converted to
  megatonnes via TONNES_PER_MEGATONNE. Change this constant if your data uses a
  different unit.
  """
  TONNES_PER_MEGATONNE = 1_000_000

  ghg_time = df[['completion_date', 'ghg_reduction']].dropna()
  if ghg_time.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No GHG data available'))
    return fig

  ghg_time = ghg_time.copy()
  ghg_time['year'] = pd.to_datetime(ghg_time['completion_date']).dt.year
  min_year = int(ghg_time['year'].min())
  max_year = 2050
  years = range(min_year, max_year + 1)

  # ── Year-by-year additions: new reduction capacity commissioned each year (Mt) ──
  additions = ghg_time.groupby('year')['ghg_reduction'].sum() / TONNES_PER_MEGATONNE
  counts    = ghg_time.groupby('year')['ghg_reduction'].count()

  # ── Cumulative lifetime reductions through 2050 (Mt) ──
  cumulative_lifetime = []
  for year in years:
    total = 0
    for _, project in ghg_time.iterrows():
      if project['year'] <= year:
        years_operating = year - project['year'] + 1
        total += project['ghg_reduction'] * years_operating
    cumulative_lifetime.append({
      'year': year,
      'cumulative_reduction': total / TONNES_PER_MEGATONNE
    })
  lifetime_df = pd.DataFrame(cumulative_lifetime)

  fig = make_subplots(
    rows=2, cols=1,
    subplot_titles=(
      'Annual Reduction Capacity Added Each Year',
      'Cumulative Lifetime Reductions (through 2050)'
    ),
    vertical_spacing=0.15,
  )

  # Subplot 1 — year-by-year additions as bars
  fig.add_trace(
    go.Bar(
      x=additions.index, y=additions.values,
      marker_color=dunsparce_colors[4],
      showlegend=False,
      text=[f'{v:,.2f}' for v in additions.values],
      textposition='outside',
      textfont=dict(family=FONT_FAMILY, size=10, color='gray'),
      customdata=list(counts.values),
      hovertemplate='<b>Year: %{x}</b><br>Added: %{y:,.3f} Mt CO2e<br>%{customdata} projects<extra></extra>'
    ),
    row=1, col=1
  )

  # Subplot 2 — cumulative lifetime reductions (filled area through 2050)
  fig.add_trace(
    go.Scatter(
      x=lifetime_df['year'], y=lifetime_df['cumulative_reduction'],
      fill='tozeroy',
      line=dict(color=dunsparce_colors[5], width=3, shape='spline'),
      showlegend=False,
      hovertemplate='<b>Year: %{x}</b><br>Cumulative Total: %{y:,.2f} Mt CO2e<extra></extra>'
    ),
    row=2, col=1
  )

  fig.add_vline(x=2026, line_dash='dash', line_color='gray', row=2, col=1)

  fig.update_xaxes(title_text='', row=1, col=1)
  fig.update_xaxes(title_text='', range=[min_year, max_year], dtick=5, row=2, col=1)
  fig.update_yaxes(title_text='Mt CO2e / year', row=1, col=1)
  fig.update_yaxes(title_text='Cumulative Mt CO2e', row=2, col=1)

  fig.update_layout(
    title=dict(text=f'GHG Emissions Reductions (n={len(ghg_time)} projects)'),
    margin=dict(t=50, b=0, l=0, r=0),
  )
  return fig


def create_key_objectives_bar_chart(df):
  """
  Horizontal bar chart: frequency of selected key project objectives.
  (Replaces the previous lollipop chart.)
  Chart-specific: x-axis line + integer ticks, ascending sort so the largest
  bar sits at the top, value labels outside each bar.
  """
  obj_counts = df['key_objectives'].explode().value_counts().reset_index()
  obj_counts.columns = ['objective', 'count']

  if obj_counts.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No key objectives data available'))
    return fig

  # Sort ascending so the largest bar sits at the top of a horizontal chart
  obj_counts = obj_counts.sort_values('count', ascending=True)

  fig = go.Figure(go.Bar(
    x=obj_counts['count'],
    y=obj_counts['objective'],
    orientation='h',
    marker_color=dunsparce_colors[1],
    text=obj_counts['count'],
    textposition='outside',
    textfont=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),
    hovertemplate='<b>%{y}</b><br>Count: %{x}<extra></extra>',
  ))

  fig.update_layout(
    title=dict(text='Key Objectives of Community Energy Projects'),
    xaxis=dict(title='Number of projects', linecolor='grey', showline=True, tickformat='d'),
    yaxis=dict(title=''),
    showlegend=False,
    margin=dict(l=0, r=0, t=50, b=0),
  )
  return fig


# ==================== EXPORT CALLABLE ====================

@anvil.server.callable
def export_outcomes_chart(chart_key, img_b64, active_filters, chart_title=''):
  return export_figure_from_bytes(
    img_b64,
    active_filters,
    filename=f'{chart_key}_export.png',
    chart_title=chart_title,
  )