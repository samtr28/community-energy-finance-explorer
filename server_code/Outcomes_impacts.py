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

from datetime import datetime

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
    ghg_timeline, key_objectives, op_expenses
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
      'ghg_timeline', 'key_objectives', 'op_expenses',
    ]}

  # ── Build all charts and apply the display template to each ──
  return {
    'indigenous_agreements': apply_display_template(create_indigenous_agreements_chart(df_filtered)),
    'jobs_chart':            apply_display_template(create_jobs_chart(df_filtered)),
    'ghg_methodology':       apply_display_template(create_ghg_methodology_chart(df_filtered)),
    'ghg_timeline':          apply_display_template(create_ghg_charts(df_filtered)),
    'key_objectives':        apply_display_template(create_key_objectives_bar_chart(df_filtered)),
    'op_expenses':           apply_display_template(create_op_expenses_chart(df_filtered)),
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
  Single chart: cumulative lifetime GHG reductions through 2050 (filled area,
  megatonnes CO2e), annotated with policy milestone markers.

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
  all_years = list(range(min_year, max_year + 1))

  # ── Cumulative lifetime reductions through 2050 (Mt), vectorized ──
  # A project completed in year p reducing r tonnes/yr has accumulated
  # r * (Y - p + 1) by year Y (>= p). Summed across projects, the
  # year-over-year increment equals the total annual reduction capacity
  # operating that year, so the cumulative series is the double cumulative
  # sum of the annual capacity commissioned each year. Years beyond 2050
  # are dropped by the reindex, matching the original loop's behaviour.
  annual_capacity = (
    ghg_time.groupby('year')['ghg_reduction'].sum()
      .reindex(all_years, fill_value=0)
  )
  cumulative_tonnes = annual_capacity.cumsum().cumsum()
  lifetime_df = pd.DataFrame({
    'year': all_years,
    'cumulative_reduction': cumulative_tonnes.values / TONNES_PER_MEGATONNE,
  })

  fig = go.Figure()
  fig.add_trace(
    go.Scatter(
      x=lifetime_df['year'], y=lifetime_df['cumulative_reduction'],
      fill='tozeroy',
      line=dict(color=dunsparce_colors[5], width=3, shape='spline'),
      showlegend=False,
      hovertemplate='<b>Year: %{x}</b><br>Cumulative Total: %{y:,.2f} Mt CO2e<extra></extra>'
    )
  )

  # ── Milestone markers ──
  # Edit this list to taste. Each milestone is drawn only if it falls within the
  # data range [min_year, max_year]; labels sit at the top of the plot area and
  # are anchored inward at the chart edges so they don't clip.
  current_year = datetime.now().year
  milestones = [
    (current_year, 'Today'),
    (2030, '2030 target'),
    (2050, 'Net-zero 2050'),
  ]
  for m_year, m_label in milestones:
    if not (min_year <= m_year <= max_year):
      continue
    if m_year >= max_year:
      xanchor = 'right'
    elif m_year <= min_year:
      xanchor = 'left'
    else:
      xanchor = 'center'
    fig.add_vline(x=m_year, line_dash='dash', line_color='gray')
    fig.add_annotation(
      x=m_year, y=1.0, yref='paper', xanchor=xanchor,
      text=m_label, showarrow=False, yshift=8,
      font=dict(family=FONT_FAMILY, size=11, color='gray'),
    )

  fig.update_xaxes(title_text='', range=[min_year, max_year], dtick=5)
  fig.update_yaxes(title_text='Cumulative Mt CO2e')

  fig.update_layout(
    title=dict(text=f'Cumulative Lifetime GHG Reductions through 2050 (n={len(ghg_time)} projects)'),
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


def create_op_expenses_chart(df):
  """
  Donut chart: operational financial health. Shows the distribution of
  operational-expense coverage status, with a center annotation giving the
  headline share of projects with a positive ('Yes…') status.

  Chart-specific: hole size, slice colors (dunsparce palette), and the center
  percentage annotation (explicit font preserved through apply_display_template).
  """
  counts = df['op_expenses'].fillna('No data').value_counts().reset_index()
  counts.columns = ['status', 'count']

  total = counts['count'].sum()
  if total == 0:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No operational expenses data'))
    return fig

  # Headline: % of projects with a positive ('Yes…') status
  covered = counts.loc[counts['status'].str.startswith('Yes', na=False), 'count'].sum()
  pct_covered = covered / total * 100

  fig = go.Figure(go.Pie(
    labels=counts['status'],
    values=counts['count'],
    hole=0.55,
    sort=False,
    textinfo='percent',
    marker=dict(colors=[dunsparce_colors[i % len(dunsparce_colors)] for i in range(len(counts))]),
  ))

  # Center headline — explicit font so it survives apply_display_template
  fig.add_annotation(
    text=f"<b>{pct_covered:.0f}%</b><br><span style='font-size:11px'>opex covered</span>",
    x=0.5, y=0.5, showarrow=False,
    font=dict(family=FONT_FAMILY, size=22, color=FONT_COLOR),
  )

  fig.update_layout(
    title=dict(text='Operational Financial Health'),
    margin=dict(t=50, b=0, l=0, r=0),
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