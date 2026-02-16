import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import pandas as pd
import numpy as np
from .config import COLOUR_MAPPING, gradient_palette, dunsparce_colors, get_owner_type_colors
from .Global_Server_Functions import get_data
import plotly.graph_objects as go
import plotly.express as px
import textwrap
from plotly.subplots import make_subplots

@anvil.server.callable
def get_all_outcomes_charts(provinces=None, proj_types=None, stages=None,
                            indigenous_ownership=None, project_scale=None):
  """
    Single server call that returns ALL outcomes/impacts chart figures at once.
    """
  # Load raw data
  df = get_data()

  # Apply filters
  df_filtered = apply_filters(df, provinces, proj_types, stages, 
                              indigenous_ownership, project_scale)

  if df_filtered.empty:
    empty_fig = go.Figure()
    empty_fig.update_layout(title="No data available for selected filters")
    return {
      'indigenous_agreements': empty_fig,
      'jobs_chart': empty_fig,
      'ghg_methodology': empty_fig,
      'ghg_timeline': empty_fig
    }

    # ========== CHART 1: Indigenous Agreements Pie ==========
  agreements_list = []
  for agreement in df_filtered['indigenous_agreements']:
    if isinstance(agreement, list):
      for a in agreement:
        agreements_list.append(a)

  if agreements_list:
    agreements_counts = pd.Series(agreements_list).value_counts()
    indigenous_fig = go.Figure(data=[
      go.Pie(labels=agreements_counts.index, values=agreements_counts.values)
    ])
    indigenous_fig.update_layout(
      title='Distribution of Indigenous Agreement Types',
      plot_bgcolor='rgba(0, 0, 0, 0)',
      paper_bgcolor='rgba(0, 0, 0, 0)',
      margin=dict(t=50, b=0, l=0, r=0)
    )
  else:
    indigenous_fig = go.Figure()
    indigenous_fig.update_layout(title="No indigenous agreements data")

    # ========== CHART 2: Jobs by Phase ==========
  jobs_list = []
  for job_entries in df_filtered['jobs']:
    if isinstance(job_entries, list):
      for entry in job_entries:
        jobs_list.append(entry)

  if jobs_list:
    jobs_df = pd.DataFrame(jobs_list)
    grouped = jobs_df.groupby('phase')[['full_time', 'part_time']].sum().fillna(0)
    reporting_counts = jobs_df.groupby('phase').agg({
      'full_time': lambda x: x.notna().sum(),
      'part_time': lambda x: x.notna().sum()
    })
    total_projects = len(df_filtered)

    jobs_fig = go.Figure(data=[
      go.Bar(name='Full-time', x=grouped.index, y=grouped['full_time']),
      go.Bar(name='Part-time', x=grouped.index, y=grouped['part_time'])
    ])

    bar_width = 0.4
    for i, phase in enumerate(grouped.index):
      jobs_fig.add_annotation(
        x=i - bar_width/2,
        y=grouped.loc[phase, 'full_time'],
        text=f"{reporting_counts.loc[phase, 'full_time']} projects<br>{grouped.loc[phase, 'full_time']:.0f} jobs",
        showarrow=False,
        font=dict(size=12, color='gray'),
        yshift=20
      )
      jobs_fig.add_annotation(
        x=i + bar_width/2,
        y=grouped.loc[phase, 'part_time'],
        text=f"{reporting_counts.loc[phase, 'part_time']} projects<br>{grouped.loc[phase, 'part_time']:.0f} jobs",
        showarrow=False,
        font=dict(size=12, color='gray'),
        yshift=20
      )

    jobs_fig.update_layout(
      barmode='group',
      title=f'Jobs by Phase: Full-time vs Part-time (Total Projects: {total_projects})',
      xaxis_title='',
      yaxis_title='',
      showlegend=True,
      legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
      plot_bgcolor='rgba(0, 0, 0, 0)',
      paper_bgcolor='rgba(0, 0, 0, 0)',
      margin=dict(t=50, b=50, l=50, r=50)
    )
  else:
    jobs_fig = go.Figure()
    jobs_fig.update_layout(title="No jobs data")

    # ========== CHART 3: GHG Methodology Treemaps ==========
  tools_list = []
  for tool_entries in df_filtered['ghg_tools']:
    if isinstance(tool_entries, list):
      for tool in tool_entries:
        tools_list.append(tool)

  who_counts = df_filtered['ghg_who'].value_counts()

  if tools_list or not who_counts.empty:
    tools_counts = pd.Series(tools_list).value_counts() if tools_list else pd.Series()

    methodology_fig = make_subplots(
      rows=1, cols=2,
      specs=[[{'type':'treemap'}, {'type':'treemap'}]],
      subplot_titles=('GHG Reduction Tools', 'Who Calculated GHG Reductions')
    )

    if not tools_counts.empty:
      methodology_fig.add_trace(
        go.Treemap(
          labels=tools_counts.index,
          parents=[''] * len(tools_counts),
          values=tools_counts.values,
          textinfo='label+value',
          marker=dict(colorscale='Blues')
        ),
        row=1, col=1
      )

    if not who_counts.empty:
      methodology_fig.add_trace(
        go.Treemap(
          labels=who_counts.index,
          parents=[''] * len(who_counts),
          values=who_counts.values,
          textinfo='label+value',
          marker=dict(colorscale='Oranges')
        ),
        row=1, col=2
      )

    methodology_fig.update_layout(
      title_text='GHG Reduction Methodology',
      height=500,
      plot_bgcolor='rgba(0, 0, 0, 0)',
      paper_bgcolor='rgba(0, 0, 0, 0)',
      margin=dict(t=50, b=0, l=0, r=0)
    )
  else:
    methodology_fig = go.Figure()
    methodology_fig.update_layout(title="No GHG methodology data")

    # ========== CHART 4: GHG Timeline (3 stacked charts) ==========
  ghg_timeline_fig = create_ghg_timeline_chart(df_filtered)

  return {
    'indigenous_agreements': indigenous_fig,
    'jobs_chart': jobs_fig,
    'ghg_methodology': methodology_fig,
    'ghg_timeline': ghg_timeline_fig
  }


def create_ghg_timeline_chart(df):
  """Create the GHG emissions reduction timeline chart"""
  # Filter projects with GHG data
  ghg_time = df[['completion_date', 'ghg_reduction']].dropna()

  if ghg_time.empty:
    empty_fig = go.Figure()
    empty_fig.update_layout(title="No GHG data available")
    return empty_fig

  ghg_time['year'] = pd.to_datetime(ghg_time['completion_date']).dt.year

  # Create year range
  min_year = ghg_time['year'].min()
  max_year = max(ghg_time['year'].max(), 2030)
  years = range(min_year, max_year + 1)

  # Calculate annual impact
  annual_impact = []
  for year in years:
    total = ghg_time[ghg_time['year'] <= year]['ghg_reduction'].sum()
    annual_impact.append({'year': year, 'annual_reduction': total})
  impact_df = pd.DataFrame(annual_impact)

  # Calculate cumulative lifetime
  cumulative_lifetime = []
  for year in years:
    total = 0
    for _, project in ghg_time.iterrows():
      if project['year'] <= year:
        years_operating = year - project['year'] + 1
        total += project['ghg_reduction'] * years_operating
    cumulative_lifetime.append({'year': year, 'cumulative_reduction': total})
  lifetime_df = pd.DataFrame(cumulative_lifetime)

  # Get project data by year
  project_years = ghg_time.groupby('year').agg({
    'ghg_reduction': 'sum',
    'year': 'count'
  }).rename(columns={'year': 'count'})

  # Calculate 2026 breakdown by type
  ghg_by_type = []
  for idx, row in df.iterrows():
    if pd.notna(row['ghg_reduction']) and pd.notna(row['completion_date']):
      year = pd.to_datetime(row['completion_date']).year
      proj_types = row.get('project_type', [])

      if isinstance(proj_types, list) and len(proj_types) > 0:
        reduction_per_type = row['ghg_reduction'] / len(proj_types)
        for proj_type in proj_types:
          ghg_by_type.append({
            'year': year,
            'project_type': proj_type,
            'ghg_reduction': reduction_per_type
          })

  ghg_type_df = pd.DataFrame(ghg_by_type)
  current_by_type = ghg_type_df[ghg_type_df['year'] <= 2026].groupby('project_type')['ghg_reduction'].sum().reset_index()
  current_by_type = current_by_type.sort_values('ghg_reduction', ascending=True)

  # Create figure
  fig = make_subplots(
    rows=3, cols=1,
    subplot_titles=('Annual Reduction Capacity', 'Cumulative Lifetime Reductions', '2026 Annual Reduction Capacity by Project Type'),
    vertical_spacing=0.12,
    row_heights=[0.35, 0.35, 0.30]
  )

  # Chart 1: Annual capacity
  fig.add_trace(
    go.Scatter(
      x=impact_df['year'],
      y=impact_df['annual_reduction'],
      fill='tozeroy',
      line=dict(color='#2ECC71', width=3, shape='spline'),
      showlegend=False,
      hovertemplate='<b>Year: %{x}</b><br>Annual Reduction: %{y:,.0f} tonnes CO2e<extra></extra>'
    ),
    row=1, col=1
  )

  # Chart 2: Cumulative lifetime
  fig.add_trace(
    go.Scatter(
      x=lifetime_df['year'],
      y=lifetime_df['cumulative_reduction'],
      fill='tozeroy',
      line=dict(color='#27AE60', width=3, shape='spline'),
      showlegend=False,
      hovertemplate='<b>Year: %{x}</b><br>Cumulative Total: %{y:,.0f} tonnes CO2e<extra></extra>'
    ),
    row=2, col=1
  )

  # Chart 3: 2026 breakdown
  colors = ['#2ECC71', '#3498DB', '#E74C3C', '#F39C12', '#9B59B6', '#1ABC9C', '#E67E22', '#95A5A6']
  if not current_by_type.empty:
    fig.add_trace(
      go.Bar(
        y=current_by_type['project_type'],
        x=current_by_type['ghg_reduction'],
        orientation='h',
        marker=dict(color=[colors[i % len(colors)] for i in range(len(current_by_type))]),
        showlegend=False,
        hovertemplate='<b>%{y}</b><br>%{x:,.0f} tonnes CO2e/year<extra></extra>'
      ),
      row=3, col=1
    )

    # Add annotations
  for year, row in project_years.iterrows():
    if year >= 2015:
      year_total = impact_df[impact_df['year'] == year]['annual_reduction'].values[0]
      fig.add_annotation(
        x=year,
        y=year_total,
        text=f"+{row['ghg_reduction']:.0f}<br>({int(row['count'])} projects)",
        showarrow=True,
        arrowhead=2,
        arrowsize=1,
        arrowwidth=2,
        arrowcolor='gray',
        ax=0,
        ay=-40,
        font=dict(size=9, color='gray'),
        row=1, col=1
      )

    # Add "Today" line
  fig.add_vline(x=2026, line_dash="dash", line_color="gray", row=1, col=1)
  fig.add_vline(x=2026, line_dash="dash", line_color="gray", row=2, col=1)

  # Set axes
  fig.update_xaxes(title_text="Year", range=[2015, max_year], dtick=1, row=1, col=1)
  fig.update_xaxes(title_text="Year", range=[2015, max_year], dtick=1, row=2, col=1)
  fig.update_xaxes(title_text="Tonnes CO2e/year", row=3, col=1)

  fig.update_yaxes(title_text="Tonnes CO2e/year", row=1, col=1)
  fig.update_yaxes(title_text="Total Tonnes CO2e", row=2, col=1)
  fig.update_yaxes(title_text="", row=3, col=1)

  fig.update_layout(
    title_text=f'GHG Emissions Reductions (n={len(ghg_time)} projects)',
    height=1000,
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    margin=dict(t=50, b=50, l=50, r=50)
  )

  return fig

def apply_filters(df, provinces=None, proj_types=None, stages=None, 
                  indigenous_ownership=None, project_scale=None):
  """
    Apply filters to dataframe. Returns filtered copy.
    Handles filtering by province, project type, stage, indigenous ownership, and project scale.
    """
  if df.empty:
    return df

  df = df.copy()

  if provinces:
    df = df[df["province"].isin(provinces)]

  if proj_types:
    # Handle project_type as list column
    df = df[df["project_type"].apply(lambda x: any(t in x for t in proj_types) if isinstance(x, list) else False)]

  if stages:
    df = df[df["stage"].isin(stages)]

  if indigenous_ownership:
    df = df[df["indigenous_ownership"].isin(indigenous_ownership)]

  if project_scale:
    df = df[df["project_scale"].isin(project_scale)]

  return df