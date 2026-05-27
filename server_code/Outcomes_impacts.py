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
import textwrap


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
    ghg_timeline, key_objectives, op_expenses,
    return_expectations, end_use_composition
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
      'return_expectations', 'end_use_composition',
    ]}

  # ── Build all charts and apply the display template to each ──
  return {
    'indigenous_agreements': apply_display_template(create_indigenous_agreements_chart(df_filtered)),
    'jobs_chart':            apply_display_template(create_jobs_chart(df_filtered)),
    'ghg_methodology':       apply_display_template(create_ghg_methodology_chart(df_filtered)),
    'ghg_timeline':          apply_display_template(create_ghg_charts(df_filtered)),
    'key_objectives':        apply_display_template(create_key_objectives_bar_chart(df_filtered)),
    'op_expenses':           apply_display_template(create_op_expenses_chart(df_filtered)),
    'return_expectations':   apply_display_template(create_return_expectations_chart(df_filtered)),
    'end_use_composition':   apply_display_template(create_end_use_composition_chart(df_filtered)),
  }


# ==================== CHART CREATION ====================
# Each function sets only chart-specific properties.
# Generic styling (backgrounds, fonts, title size, margins) is handled
# by apply_display_template() in get_all_outcomes_charts() above.
# Title text is still set here since it is chart-specific content.

def create_indigenous_agreements_chart(df):
  """
  100% stacked bar: share of each indigenous agreement type across all
  agreements (one bar, segments sum to 100%).

  Customize AGREEMENT_COLORS below to set per-type colours; any type without
  an entry falls back to the dunsparce palette by position.
  """
  # ── Customize colours here ─────────────────────────────────────
  # Map agreement-type label -> hex colour. Keys must match the strings stored
  # in the indigenous_agreements lists. Unlisted types use the dunsparce palette.
  AGREEMENT_COLORS = {
     'Impact Benefit Agreement': dunsparce_colors[3],
     'One-time payment':       dunsparce_colors[4],
     'Memorandum of Understanding': dunsparce_colors[1],
    'No agreements': dunsparce_colors[19],
    'Resource/Revenue Sharing Agreement': dunsparce_colors[9],
    "Don't know": dunsparce_colors[16],
    "Other": dunsparce_colors[13]
    
  }
  # ───────────────────────────────────────────────────────────────

  agreements_list = []
  for agreement in df['indigenous_agreements']:
    if isinstance(agreement, list):
      agreements_list.extend(agreement)

  if not agreements_list:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No indigenous agreements data'))
    return fig

  agreements_counts = pd.Series(agreements_list).value_counts()
  total = agreements_counts.sum()

  fig = go.Figure()
  for i, (label, count) in enumerate(agreements_counts.items()):
    pct = count / total * 100
    color = AGREEMENT_COLORS.get(label) or dunsparce_colors[i % len(dunsparce_colors)]
    fig.add_trace(go.Bar(
      y=['Agreements'], x=[pct],
      name=label, orientation='h',
      marker_color=color,
      text=[f'{pct:.0f}%'],
      textposition='inside', insidetextanchor='middle',
      textfont=dict(family=FONT_FAMILY, size=12, color='white'),
      hovertemplate=f'<b>{label}</b><br>{count} agreements (%{{x:.1f}}%)<extra></extra>',
    ))

  fig.update_layout(
    barmode='stack',
    title=dict(text='Types of Indigenous Partnership Agreements Reported by Project in the Dataset'),
    xaxis=dict(title='', range=[0, 100], ticksuffix='%', showgrid=False),
    yaxis=dict(title='', showticklabels=False),
    legend=dict(orientation='h', yanchor='top', y=-0.15, xanchor='center', x=0.5),
    margin=dict(t=50, b=0, l=0, r=0),
    height=260,
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
    go.Bar(name='Full-time', x=grouped.index, y=grouped['full_time'], marker_color=dunsparce_colors[12]),
    go.Bar(name='Part-time', x=grouped.index, y=grouped['part_time'], marker_color=dunsparce_colors[0])
  ])

  bar_width = 0.4
  for i, phase in enumerate(grouped.index):
    for x_offset, col in [(-bar_width / 2, 'full_time'), (bar_width / 2, 'part_time')]:
      bar_y = grouped.loc[phase, col]
      n_responses = reporting_counts.loc[phase, col]
      n_jobs = grouped.loc[phase, col]

      # Jobs number — big, bold, black
      fig.add_annotation(
        x=i + x_offset, y=bar_y,
        text=f"<b>{n_jobs:.0f} jobs</b>",
        showarrow=False, yshift=28,
        font=dict(family=FONT_FAMILY, size=16, color='black'),
      )
      # Response count — small, grey, below
      fig.add_annotation(
        x=i + x_offset, y=bar_y,
        text=f"{n_responses} responses",
        showarrow=False, yshift=10,
        font=dict(family=FONT_FAMILY, size=10, color='gray'),
      )

  fig.update_layout(
    barmode='group',
    title=dict(text='Jobs Created During Construction and Operation by Projects in the Dataset'),
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

  # ── Customize here ─────────────────────────────────────────────
  # Wrap long treemap tile labels. Auto-wrap any label longer than N chars at
  # word boundaries; set to None to disable. Explicit overrides win.
  LABEL_WRAP_WIDTH = 16
  LABEL_OVERRIDES = {
    # 'Greenhouse Gas Protocol': 'Greenhouse Gas<br>Protocol',
  }
  # ───────────────────────────────────────────────────────────────

  def _wrap(label):
    if label in LABEL_OVERRIDES:
      return LABEL_OVERRIDES[label]
    if LABEL_WRAP_WIDTH:
      return '<br>'.join(textwrap.wrap(str(label), LABEL_WRAP_WIDTH)) or str(label)
    return str(label)

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
        labels=[_wrap(l) for l in tools_counts.index], parents=[''] * len(tools_counts),
        values=tools_counts.values, textinfo='label+value',
        marker=dict(colors=tools_colors, line=dict(width=2, color='white'))
      ),
      row=1, col=1
    )

  if not who_counts.empty:
    who_colors = [gradient_palette[i % len(gradient_palette)] for i in range(len(who_counts))]
    fig.add_trace(
      go.Treemap(
        labels=[_wrap(l) for l in who_counts.index], parents=[''] * len(who_counts),
        values=who_counts.values, textinfo='label+value',
        marker=dict(colors=who_colors, line=dict(width=2, color='white'))
      ),
      row=1, col=2
    )

  fig.update_layout(
    title=dict(text='GHG Reduction Calculation Methods Used by Projects in the Dataset'),
    height=500,
    margin=dict(t=50, b=0, l=0, r=0),
  )
  return fig


def create_ghg_charts(df):
  """
  Single chart: cumulative lifetime GHG reductions through 2050 (filled area,
  megatonnes CO2e), with a "Now" reference line and value callouts showing the
  cumulative total reached by 2030 and 2050.

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

  # ── "Now" reference line ──
  current_year = datetime.now().year
  if min_year <= current_year <= max_year:
    fig.add_vline(x=current_year, line_dash='dash', line_color='gray')
    fig.add_annotation(
      x=current_year, y=1.0, yref='paper', xanchor='center',
      text='Now', showarrow=False, yshift=8,
      font=dict(family=FONT_FAMILY, size=11, color='gray'),
    )

  # ── Value callouts: cumulative total reached by 2030 and 2050 ──
  # (year, x-offset px, y-offset px, text anchor) — offsets keep the 2050
  # label tucked off the right edge.
  callouts = [
    (2030, 0,   -40, 'center'),
    (2050, -45, -25, 'right'),
  ]
  marker_x, marker_y = [], []
  for cy, ax, ay, xanchor in callouts:
    if not (min_year <= cy <= max_year):
      continue
    yval = float(lifetime_df.loc[lifetime_df['year'] == cy, 'cumulative_reduction'].iloc[0])
    marker_x.append(cy)
    marker_y.append(yval)
    fig.add_annotation(
      x=cy, y=yval, xanchor=xanchor,
      text=f'<b>{yval:,.1f} Mt</b><br>by {cy}',
      showarrow=True, arrowhead=2, arrowsize=1, arrowcolor='gray',
      ax=ax, ay=ay,
      font=dict(family=FONT_FAMILY, size=11, color=FONT_COLOR),
    )

  # Marker dots anchoring each callout to the curve
  if marker_x:
    fig.add_trace(go.Scatter(
      x=marker_x, y=marker_y, mode='markers',
      marker=dict(size=9, color=dunsparce_colors[5], line=dict(width=2, color='white')),
      showlegend=False, hoverinfo='skip',
    ))

  fig.update_xaxes(title_text='', range=[min_year, max_year], dtick=5)
  fig.update_yaxes(title_text='Cumulative Mt CO2e')

  fig.update_layout(
    title=dict(text=f'Cumulative GHG Reductions Through 2050 From Projects in the Dataset (n={len(ghg_time)} projects)'),
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
    title=dict(text='Reported Objectives of Community Energy Projects In Canada'),
    xaxis=dict(title='Number of projects', linecolor='grey', showline=True, tickformat='d'),
    yaxis=dict(title=''),
    showlegend=False,
    margin=dict(l=0, r=0, t=50, b=0),
  )
  return fig


def create_op_expenses_chart(df):
  """
  Donut chart: operational financial health — distribution of operational-
  expense coverage status, shown in a fixed category order.

  Customize CATEGORY_ORDER, CATEGORY_COLORS and COVERED_CATEGORIES below to
  match the exact strings stored in your `op_expenses` column.
  """
  # ── Customize here ─────────────────────────────────────────────
  # Slice order (clockwise from 12 o'clock). MUST match your data strings.
  CATEGORY_ORDER = [
    'Yes, consistently',
    'Yes, but with occasional shortfalls',
    'No, currently operating at a deficit',
    'Not yet operational',
    'Not sure / Prefer not to say',
  ]
  # Per-category colours. Leave a value as None to fall back to the dunsparce
  # palette (by position). Fill in your own hex codes here.
  CATEGORY_COLORS = {
    'Yes, consistently':                    dunsparce_colors[14],
    'Yes, but with occasional shortfalls':  dunsparce_colors[2],
    'No, currently operating at a deficit': dunsparce_colors[6],
    'Not yet operational':                  dunsparce_colors[15],
    'Not sure / Prefer not to say':         dunsparce_colors[19],
  }
  # Categories counted toward the centre "% cover opex" headline.
  COVERED_CATEGORIES = ['Yes, consistently', 'Yes, but with occasional shortfalls']
  # Set False to remove the centre indicator entirely.
  SHOW_CENTER_HEADLINE = True
  # ───────────────────────────────────────────────────────────────

  counts = df['op_expenses'].value_counts()  # blanks (NaN) excluded by default
  total = counts.sum()
  if total == 0:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No operational expenses data'))
    return fig

  # Listed categories first (only those present), then any unexpected extras
  order  = [c for c in CATEGORY_ORDER if c in counts.index]
  order += [c for c in counts.index if c not in CATEGORY_ORDER]
  counts = counts.reindex(order)

  colors = [CATEGORY_COLORS.get(cat) or dunsparce_colors[i % len(dunsparce_colors)]
            for i, cat in enumerate(order)]

  # Headline % = COVERED_CATEGORIES as a share of ALL responses (denominator
  # includes not-yet-operational and unknown answers). Adjust if you'd rather
  # compute it only among operational projects.
  covered = counts.reindex(COVERED_CATEGORIES).fillna(0).sum()
  pct_covered = covered / total * 100

  fig = go.Figure(go.Pie(
    labels=list(counts.index),
    values=list(counts.values),
    hole=0.55,
    sort=False,
    direction='clockwise',
    textinfo='percent',
    marker=dict(colors=colors),
  ))

  if SHOW_CENTER_HEADLINE:
    # Explicit fonts so the headline survives apply_display_template.
    fig.add_annotation(
      text=(f"<b>{pct_covered:.0f}%</b>"
            f"<br><span style='font-size:11px'>cover opex</span>"
            f"<br><span style='font-size:10px;color:gray'>(yes, consistently<br>or minor shortfalls)</span>"),
      x=0.5, y=0.5, showarrow=False,
      font=dict(family=FONT_FAMILY, size=20, color=FONT_COLOR),
    )

  fig.update_layout(
    title=dict(text='Operational Cost Coverage Reported by Projects In the Pilot Dataset'),
    showlegend=True,
    legend=dict(orientation='h', yanchor='top', y=-0.05, xanchor='center', x=0.5),
    margin=dict(t=50, b=0, l=0, r=0),
  )
  return fig


def create_return_expectations_chart(df):
  """
  Donut chart: return expectations — distribution of answers to whether the
  project expects a financial return, in a fixed category order. Mirrors
  create_op_expenses_chart.

  Customize CATEGORY_ORDER, CATEGORY_COLORS and POSITIVE_CATEGORIES below to
  match the exact strings stored in your `return_expectation` column.
  """
  # ── Customize here ─────────────────────────────────────────────
  # Slice order (clockwise from 12 o'clock). MUST match your data strings.
  CATEGORY_ORDER = [
    'Yes',
    'No',
    'Too early to tell',
    "Don't know",
    'Not applicable',
  ]
  # Per-category colours. Leave a value as None to fall back to the dunsparce
  # palette (by position). Fill in your own hex codes here.
  CATEGORY_COLORS = {
    'Yes':               dunsparce_colors[14],
    'No':                dunsparce_colors[6],
    'Too early to tell': dunsparce_colors[15],
    "Don't know":        dunsparce_colors[19],
    'Not applicable':    dunsparce_colors[18],
  }
  # Categories counted toward the centre "% expect a return" headline.
  POSITIVE_CATEGORIES = ['Yes']
  # Set False to remove the centre indicator entirely.
  SHOW_CENTER_HEADLINE = True
  # ───────────────────────────────────────────────────────────────

  counts = df['return_expectation'].value_counts()  # blanks (NaN) excluded by default
  total = counts.sum()
  if total == 0:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No return expectations data'))
    return fig

  # Listed categories first (only those present), then any unexpected extras
  order  = [c for c in CATEGORY_ORDER if c in counts.index]
  order += [c for c in counts.index if c not in CATEGORY_ORDER]
  counts = counts.reindex(order)

  colors = [CATEGORY_COLORS.get(cat) or dunsparce_colors[i % len(dunsparce_colors)]
            for i, cat in enumerate(order)]

  # Headline % = POSITIVE_CATEGORIES as a share of ALL responses.
  positive = counts.reindex(POSITIVE_CATEGORIES).fillna(0).sum()
  pct_positive = positive / total * 100

  fig = go.Figure(go.Pie(
    labels=list(counts.index),
    values=list(counts.values),
    hole=0.55,
    sort=False,
    direction='clockwise',
    textinfo='percent',
    marker=dict(colors=colors),
  ))

  if SHOW_CENTER_HEADLINE:
    # Explicit fonts so the headline survives apply_display_template.
    fig.add_annotation(
      text=(f"<b>{pct_positive:.0f}%</b>"
            f"<br><span style='font-size:11px'>meeting return<br>expectations</span>"),
      x=0.5, y=0.5, showarrow=False,
      font=dict(family=FONT_FAMILY, size=20, color=FONT_COLOR),
    )

  fig.update_layout(
    title=dict(text='Reported Achievement of Financial Return Expectations in the Pilot Dataset'),
    showlegend=True,
    legend=dict(orientation='h', yanchor='top', y=-0.05, xanchor='center', x=0.5),
    margin=dict(t=50, b=0, l=0, r=0),
  )
  return fig


def create_end_use_composition_chart(df):
  """
  100% stacked horizontal bar: end-use composition within each primary
  technology (the "E4 composition" view). For each technology the bar is split
  into energy end-use segments whose shares sum to 100%.
 
  Mirrors _build_uses_long from the Energy explorer:
    * technology = the FIRST entry of the project_type list (primary tech),
      or 'Unknown' if the list is empty.
    * end-uses   = each entry of the uses_all list.
  """
  # ── Customize here ─────────────────────────────────────────────
  TECH_COL = 'project_type'   # primary technology = first element of this list
  USE_COL  = 'uses_all'       # list of energy end-uses per project
  # Optional per-end-use colours; unlisted uses fall back to the dunsparce
  # palette. (Swap in px.colors.qualitative.Pastel for the reference look.)
  USE_COLORS = {
    # 'Heating':     '#a6cee3',
    # 'Electricity': '#b2df8a',
  }
  # Wrap long legend labels. Two options (overrides win over auto-wrap):
  #  (a) explicit — put <br> exactly where you want the break:
  USE_LABEL_OVERRIDES = {
    'Used to optimize system performance and operations': 'Used to optimize system<br>performance & operations'
    # 'Electricity for community buildings': 'Electricity for<br>community buildings',
    # 'Heating and hot water':               'Heating and<br>hot water',
  }
  #  (b) automatic — wrap ANY label longer than N chars at word boundaries.
  #      Set to None to disable (then only the explicit overrides above apply).
  AUTO_WRAP_WIDTH = None   # e.g. 16
  # ───────────────────────────────────────────────────────────────

  def _to_list(v):
    if isinstance(v, list):
      return v
    return [] if pd.isna(v) else [v]

  def _primary(v):
    items = _to_list(v)
    return items[0] if items else 'Unknown'

  def _label(use):
    """Legend display label: explicit override, else optional auto-wrap, else raw."""
    if use in USE_LABEL_OVERRIDES:
      return USE_LABEL_OVERRIDES[use]
    if AUTO_WRAP_WIDTH:
      return '<br>'.join(textwrap.wrap(str(use), AUTO_WRAP_WIDTH)) or str(use)
    return str(use)

  long = pd.DataFrame({
    'tech': df[TECH_COL].apply(_primary),
    'use':  df[USE_COL].apply(_to_list),
  }).explode('use').dropna(subset=['use'])

  if long.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No end-use data available'))
    return fig

  # Count (tech, use) pairs, then normalize within each technology → 100%
  ct = long.groupby(['tech', 'use']).size().unstack(fill_value=0)
  share = ct.div(ct.sum(axis=1), axis=0)

  # Order technologies so those with the most projects sit at the top
  share = share.loc[ct.sum(axis=1).sort_values(ascending=True).index]
  techs = list(share.index)

  fig = go.Figure()
  for i, use in enumerate(share.columns):
    color = USE_COLORS.get(use) or dunsparce_colors[i % len(dunsparce_colors)]
    fig.add_trace(go.Bar(
      y=techs, x=share[use].values,        # shares as fractions 0..1
      name=_label(use), orientation='h',   # wrapped label in the legend
      marker_color=color,
      hovertemplate='<b>%{y}</b><br>' + str(use) + ': %{x:.0%}<extra></extra>',
    ))

  fig.update_layout(
    barmode='stack',
    title=dict(text='End-use Composition within each Technology (100% stacked)'),
    xaxis=dict(title='Share of end-uses', tickformat='.0%', range=[0, 1]),
    yaxis=dict(title=''),
    showlegend=True,
    legend=dict(
      orientation='h', yanchor='top', y=-0.15, xanchor='center', x=0.5,
      entrywidthmode='fraction', entrywidth=0.33,  # ~3 entries per row; 0.5→2, 0.25→4
      font=dict(size=11),
    ),
    margin=dict(t=50, b=0, l=0, r=0),
    height=140 + 70 * len(techs),
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
