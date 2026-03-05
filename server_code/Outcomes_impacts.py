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


def create_indigenous_agreements_chart(df):
  """Create donut chart showing distribution of indigenous agreement types"""
  agreements_list = []
  for agreement in df['indigenous_agreements']:
    if isinstance(agreement, list):
      for a in agreement:
        agreements_list.append(a)

  if not agreements_list:
    fig = go.Figure()
    fig.update_layout(title=dict(text="No indigenous agreements data", font=dict(family='Arial, sans-serif', size=16, color='black')))
    return fig

  agreements_counts = pd.Series(agreements_list).value_counts()
  fig = go.Figure(data=[
    go.Pie(
      labels=agreements_counts.index,
      values=agreements_counts.values,
      hole=0.4,
      showlegend=False,
      marker=dict(colors=dunsparce_colors[:len(agreements_counts)])
    )
  ])
  fig.update_layout(
    title=dict(text='Project Agreements with Indigenous Communities', font=dict(family='Arial, sans-serif', size=16, color='black')),
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    margin=dict(t=50, b=0, l=0, r=0)
  )
  return fig


def create_jobs_chart(df):
  """Create grouped bar chart showing jobs by phase"""
  jobs_list = []
  for job_entries in df['jobs']:
    if isinstance(job_entries, list):
      for entry in job_entries:
        jobs_list.append(entry)

  if not jobs_list:
    fig = go.Figure()
    fig.update_layout(title=dict(text="No jobs data", font=dict(family='Arial, sans-serif', size=16, color='black')))
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
    fig.add_annotation(
      x=i - bar_width/2,
      y=grouped.loc[phase, 'full_time'],
      text=f"{reporting_counts.loc[phase, 'full_time']} projects<br>{grouped.loc[phase, 'full_time']:.0f} jobs",
      showarrow=False,
      font=dict(size=12, color='gray'),
      yshift=20
    )
    fig.add_annotation(
      x=i + bar_width/2,
      y=grouped.loc[phase, 'part_time'],
      text=f"{reporting_counts.loc[phase, 'part_time']} projects<br>{grouped.loc[phase, 'part_time']:.0f} jobs",
      showarrow=False,
      font=dict(size=12, color='gray'),
      yshift=20
    )

  fig.update_layout(
    barmode='group',
    title=dict(text=f'Jobs by Phase: Full-time vs Part-time (Total Projects: {total_projects})', font=dict(family='Arial, sans-serif', size=16, color='black')),
    xaxis_title='',
    yaxis_title='',
    showlegend=True,
    legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5),
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    margin=dict(t=50, b=0, l=0, r=0),
    font=dict(family='Arial, sans-serif', size=12, color='black')
  )
  return fig


def create_ghg_methodology_chart(df):
  """Create treemap charts showing GHG reduction tools and who calculated reductions"""
  tools_list = []
  for tool_entries in df['ghg_tools']:
    if isinstance(tool_entries, list):
      for tool in tool_entries:
        tools_list.append(tool)

  who_counts = df['ghg_who'].value_counts()

  if not tools_list and who_counts.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text="No GHG methodology data", font=dict(family='Arial, sans-serif', size=16, color='black')))
    return fig

  tools_counts = pd.Series(tools_list).value_counts() if tools_list else pd.Series()

  fig = make_subplots(
    rows=1, cols=2,
    specs=[[{'type': 'treemap'}, {'type': 'treemap'}]],
    subplot_titles=('GHG Reduction Tools', 'Who Calculated GHG Reductions'),
    horizontal_spacing=0.02
  )

  for annotation in fig['layout']['annotations']:
    annotation['font'] = dict(family='Arial, sans-serif', size=12, color='black')

  if not tools_counts.empty:
    tools_colors = [gradient_palette[i % len(gradient_palette)] for i in range(len(tools_counts))]
    fig.add_trace(
      go.Treemap(
        labels=tools_counts.index,
        parents=[''] * len(tools_counts),
        values=tools_counts.values,
        textinfo='label+value',
        marker=dict(colors=tools_colors, line=dict(width=2, color='white'))
      ),
      row=1, col=1
    )

  if not who_counts.empty:
    who_colors = [gradient_palette[i % len(gradient_palette)] for i in range(len(who_counts))]
    fig.add_trace(
      go.Treemap(
        labels=who_counts.index,
        parents=[''] * len(who_counts),
        values=who_counts.values,
        textinfo='label+value',
        marker=dict(colors=who_colors, line=dict(width=2, color='white'))
      ),
      row=1, col=2
    )

  fig.update_layout(
    title=dict(text='GHG Reduction Methodology', font=dict(family='Arial, sans-serif', size=16, color='black')),
    height=500,
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    margin=dict(t=50, b=0, l=0, r=0),
    font=dict(family='Arial, sans-serif', size=12, color='black')
  )
  return fig


def create_ghg_charts(df):
  """Create GHG timeline (2 subplots) + 2026 project type horizontal stacked bar (1 subplot)"""
  ghg_time = df[['completion_date', 'ghg_reduction']].dropna()

  if ghg_time.empty:
    empty_fig = go.Figure()
    empty_fig.update_layout(title="No GHG data available")
    return empty_fig

  ghg_time['year'] = pd.to_datetime(ghg_time['completion_date']).dt.year
  min_year = ghg_time['year'].min()
  max_year = max(ghg_time['year'].max(), 2030)
  years = range(min_year, max_year + 1)

  annual_impact = []
  for year in years:
    total = ghg_time[ghg_time['year'] <= year]['ghg_reduction'].sum()
    annual_impact.append({'year': year, 'annual_reduction': total})
  impact_df = pd.DataFrame(annual_impact)

  cumulative_lifetime = []
  for year in years:
    total = 0
    for _, project in ghg_time.iterrows():
      if project['year'] <= year:
        years_operating = year - project['year'] + 1
        total += project['ghg_reduction'] * years_operating
    cumulative_lifetime.append({'year': year, 'cumulative_reduction': total})
  lifetime_df = pd.DataFrame(cumulative_lifetime)

  project_years = ghg_time.groupby('year').agg(
    ghg_reduction=('ghg_reduction', 'sum'),
    count=('ghg_reduction', 'count')
  )

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

  fig = make_subplots(
    rows=3, cols=1,
    subplot_titles=(
      'Annual Reduction Capacity',
      'Cumulative Lifetime Reductions',
      '2026 Annual Reduction Capacity by Project Type'
    ),
    vertical_spacing=0.15,
    row_heights=[0.4, 0.4, 0.2]
  )

  for annotation in fig['layout']['annotations']:
    annotation['font'] = dict(family='Arial, sans-serif', size=12, color='black')

  fig.add_trace(
    go.Scatter(
      x=impact_df['year'],
      y=impact_df['annual_reduction'],
      fill='tozeroy',
      line=dict(color=dunsparce_colors[4], width=3, shape='spline'),
      showlegend=False,
      hovertemplate='<b>Year: %{x}</b><br>Annual Reduction: %{y:,.0f} tonnes CO2e<extra></extra>'
    ),
    row=1, col=1
  )

  fig.add_trace(
    go.Scatter(
      x=lifetime_df['year'],
      y=lifetime_df['cumulative_reduction'],
      fill='tozeroy',
      line=dict(color=dunsparce_colors[5], width=3, shape='spline'),
      showlegend=False,
      hovertemplate='<b>Year: %{x}</b><br>Cumulative Total: %{y:,.0f} tonnes CO2e<extra></extra>'
    ),
    row=2, col=1
  )

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

  if ghg_by_type:
    type_df = pd.DataFrame(ghg_by_type)
    current_by_type = type_df[type_df['year'] <= 2026].groupby('project_type')['ghg_reduction'].sum().reset_index()
    current_by_type = current_by_type.sort_values('ghg_reduction', ascending=False).reset_index(drop=True)

    total = current_by_type['ghg_reduction'].sum()
    current_by_type['pct'] = current_by_type['ghg_reduction'] / total * 100

    for i, type_row in current_by_type.iterrows():
      fig.add_trace(
        go.Bar(
          x=[type_row['pct']],
          y=['2026'],
          orientation='h',
          name=type_row['project_type'],
          showlegend=False,
          text=[type_row['project_type']],
          textposition='inside',
          insidetextanchor='middle',
          constraintext='inside',
          marker_color=dunsparce_colors[i % len(dunsparce_colors)],
          hovertemplate=f'<b>{type_row["project_type"]}</b><br>{type_row["pct"]:.1f}%<br>{type_row["ghg_reduction"]:,.0f} tonnes CO2e/year<extra></extra>'
        ),
        row=3, col=1
      )

  for r in [1, 2]:
    fig.add_vline(x=2026, line_dash="dash", line_color="gray", row=r, col=1)

  fig.update_xaxes(title_text="", range=[2015, max_year], dtick=1, row=1, col=1)
  fig.update_xaxes(title_text="", range=[2015, max_year], dtick=1, row=2, col=1)
  fig.update_xaxes(title_text="", range=[0, 100], ticksuffix="%", row=3, col=1)
  fig.update_yaxes(title_text="Tonnes CO2e/year", row=1, col=1)
  fig.update_yaxes(title_text="Total Tonnes CO2e", row=2, col=1)
  fig.update_yaxes(showticklabels=False, row=3, col=1)

  fig.update_layout(
    barmode='stack',
    title=dict(text=f'GHG Emissions Reductions (n={len(ghg_time)} projects)', font=dict(family='Arial, sans-serif', size=16, color='black')),
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    margin=dict(t=50, b=0, l=0, r=0),
    font=dict(family='Arial, sans-serif', size=12, color='black'),
  )
  return fig


def apply_filters(df, provinces=None, proj_types=None, stages=None,
                  indigenous_ownership=None, project_scale=None):
  if df.empty:
    return df

  df = df.copy()

  if provinces:
    df = df[df["province"].isin(provinces)]

  if proj_types:
    df = df[df["project_type"].apply(lambda x: any(t in x for t in proj_types) if isinstance(x, list) else False)]

  if stages:
    df = df[df["stage"].isin(stages)]

  if indigenous_ownership:
    df = df[df["indigenous_ownership"].isin(indigenous_ownership)]

  if project_scale:
    df = df[df["project_scale"].isin(project_scale)]

  return df

def create_key_objectives_by_project_type_chart(df):
  """Create bubble chart showing key objectives by project type with count/dollar toggle"""

  # Simple wrap function - no imports needed
  def wrap_label(text, width=40):
    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
      if current_length + len(word) + 1 <= width:
        current_line.append(word)
        current_length += len(word) + 1
      else:
        if current_line:
          lines.append(' '.join(current_line))
        current_line = [word]
        current_length = len(word)

    if current_line:
      lines.append(' '.join(current_line))

    return '<br>'.join(lines)

    # Explode both columns
  df_exploded = df.explode('project_type').explode('key_objectives')

  # Remove any NaN values
  df_exploded = df_exploded.dropna(subset=['project_type', 'key_objectives'])

  # Remove "Other" from key objectives
  df_exploded = df_exploded[df_exploded['key_objectives'] != 'Other']

  if df_exploded.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text="No key objectives data available", font=dict(family='Arial, sans-serif', size=16, color='black')))
    return fig

    # Create wrapped labels mapping
  unique_objectives = df_exploded['key_objectives'].unique()
  label_map = {obj: wrap_label(obj, width=40) for obj in unique_objectives}

  # Apply wrapped labels
  df_exploded['key_objectives_wrapped'] = df_exploded['key_objectives'].map(label_map)

  # Count combinations
  count_data = df_exploded.groupby(['project_type', 'key_objectives_wrapped']).size().reset_index(name='count')

  # Dollar amount combinations
  dollar_data = df_exploded.groupby(['project_type', 'key_objectives_wrapped'])['total_cost'].sum().reset_index(name='amount')
  dollar_data['amount_millions'] = dollar_data['amount'] / 1_000_000

  # Get sort order
  obj_order_original = df_exploded.groupby('key_objectives')['key_objectives'].count().sort_values(ascending=False).index.tolist()
  obj_order = [label_map[obj] for obj in obj_order_original]
  type_order = count_data.groupby('project_type')['count'].sum().sort_values(ascending=False).index.tolist()

  # Color mapping
  type_colors = {t: dunsparce_colors[i % len(dunsparce_colors)] for i, t in enumerate(type_order)}

  def normalize_size(values, min_size=12, max_size=45):
    if values.max() == values.min():
      return [30] * len(values)
    normalized = (values - values.min()) / (values.max() - values.min())
    return normalized * (max_size - min_size) + min_size

  def format_amount(x):
    if x >= 1000:
      return f'{x/1000:.1f}B'
    elif x >= 1:
      return f'{x:.1f}M'
    else:
      return f'{x*1000:.0f}K'

  count_sizes = normalize_size(count_data['count'])
  dollar_sizes = normalize_size(dollar_data['amount_millions'])

  fig = go.Figure()

  # Trace 1: Count view
  fig.add_trace(go.Scatter(
    x=count_data['project_type'],
    y=count_data['key_objectives_wrapped'],
    mode='markers+text',
    marker=dict(
      size=count_sizes,
      color=[type_colors[t] for t in count_data['project_type']],
    ),
    text=count_data['count'],
    textposition='middle center',
    textfont=dict(size=9, color='black', family='Arial, sans-serif'),
    hovertemplate='<b>%{y}</b><br>Project Type: %{x}<br>Count: %{text}<extra></extra>',
    visible=True,
    name='Count'
  ))

  # Trace 2: Dollar amount view
  fig.add_trace(go.Scatter(
    x=dollar_data['project_type'],
    y=dollar_data['key_objectives_wrapped'],
    mode='markers+text',
    marker=dict(
      size=dollar_sizes,
      color=[type_colors[t] for t in dollar_data['project_type']],
    ),
    text=dollar_data['amount_millions'].apply(format_amount),
    textposition='middle center',
    textfont=dict(size=8, color='black', family='Arial, sans-serif'),
    hovertemplate='<b>%{y}</b><br>Project Type: %{x}<br>Amount: $%{text}<extra></extra>',
    visible=False,
    name='Dollar Amount'
  ))

  fig.update_layout(
    title=dict(
      text='Key Objectives by Project Type',
      font=dict(family='Arial, sans-serif', size=16, color='black'),
      x=0,
      xanchor='left'
    ),
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    margin=dict(l=0, b=0, t=50, r=0),
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    xaxis=dict(
      title='',
      tickangle=-20,
      tickfont=dict(size=11, family='Arial, sans-serif', color='black'),
      showgrid=False,
      linecolor='#e0e0e0',
      categoryorder='array',
      categoryarray=type_order,
      range=[-0.5, len(type_order) - 0.5]
    ),
    yaxis=dict(
      title='',
      tickfont=dict(size=11, family='Arial, sans-serif', color='black'),
      showgrid=True,
      gridcolor='#f0f0f0',
      gridwidth=1,
      linecolor='#e0e0e0',
      categoryorder='array',
      categoryarray=obj_order[::-1],
      range=[-0.8, len(obj_order) - 0]
    ),
    showlegend=False,
    updatemenus=[dict(
      type='buttons',
      direction='left',
      buttons=[
        dict(label='Count', method='update', args=[{'visible': [True, False]}]),
        dict(label='Dollars', method='update', args=[{'visible': [False, True]}])
      ],
      pad={'r': 0, 't': 10},
      showactive=True,
      x=0.5,
      y=1.08,
      xanchor='center',
      yanchor='top',
      bgcolor='rgba(255, 255, 255, 0.8)',
      bordercolor='gray',
      borderwidth=1
    )]
  )

  return fig

def create_key_objectives_lollipop_chart(df):
  """Create lollipop chart showing key objectives frequency"""

  # Count key objectives occurrences
  obj_counts = df['key_objectives'].explode().value_counts().reset_index()
  obj_counts.columns = ['objective', 'count']

  if obj_counts.empty:
    fig = go.Figure()
    fig.update_layout(title=dict(text="No key objectives data available", font=dict(family='Arial, sans-serif', size=16, color='black')))
    return fig

    # Sort ascending for horizontal chart (highest at top)
  obj_counts = obj_counts.sort_values('count', ascending=True)
  objectives = obj_counts['objective'].tolist()
  counts = obj_counts['count'].tolist()

  # Use dunsparce color
  lollipop_color = dunsparce_colors[1]

  # Create figure
  fig = go.Figure()

  # Add lines and dots for each objective
  for i, obj in enumerate(objectives):
    # Horizontal line
    fig.add_scatter(
      x=[0, counts[i]], 
      y=[i, i],
      mode="lines", 
      line=dict(color=lollipop_color, width=6), 
      showlegend=False,
      hoverinfo='skip'
    )

    # Label annotation
    fig.add_annotation(
      text=obj, 
      x=0.2,
      y=i + 0.37, 
      xanchor="left",
      yanchor="middle",
      showarrow=False,
      font=dict(family='Arial, sans-serif', size=14, color=dunsparce_colors[5])
    )

    # Count on dot
    fig.add_annotation(
      text=f'<b>{counts[i]}</b>',
      x=counts[i], 
      y=i, 
      xanchor="center",
      yanchor="middle",
      showarrow=False,
      font=dict(color='white', family='Arial, sans-serif', size=16)
    )

    # Add dots
  fig.add_scatter(
    x=counts, 
    y=list(range(len(objectives))), 
    mode="markers", 
    marker=dict(size=30, color=lollipop_color),
    showlegend=False,
    hovertemplate='<b>%{text}</b><br>Count: %{x}<extra></extra>',
    text=objectives
  )

  # Update axes
  fig.update_xaxes(
    visible=False,
    range=[0, max(counts) * 1.15] if counts else [0, 10], 
    showline=False, 
    ticks="", 
    showticklabels=False,
    showgrid=False
  )

  fig.update_yaxes(
    visible=False,
    ticks="", 
    showticklabels=False,
    showgrid=False
  )

  # Update layout
  fig.update_layout(
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    margin=dict(l=0, r=0, t=0, b=0),
    title=dict(
      text='Selected Key Objectives of Community Energy Projects',
      font=dict(family='Arial, sans-serif', size=16, color='black'),
      x=0.01,
      xanchor='left',
      y=0.98,
      yanchor='top'
    )
  )

  return fig

@anvil.server.callable
def get_all_outcomes_charts(provinces=None, proj_types=None, stages=None,
                            indigenous_ownership=None, project_scale=None):
  """Single server call that returns ALL outcomes/impacts chart figures at once."""
  df = get_data()
  df_filtered = apply_filters(df, provinces, proj_types, stages,
                              indigenous_ownership, project_scale)

  if df_filtered.empty:
    empty_fig = go.Figure()
    empty_fig.update_layout(title="No data available for selected filters")
    return {
      'indigenous_agreements': empty_fig,
      'jobs_chart': empty_fig,
      'ghg_methodology': empty_fig,
      'ghg_timeline': empty_fig,
      'key_objectives': empty_fig, 
    }

  return {
    'indigenous_agreements': create_indigenous_agreements_chart(df_filtered),
    'jobs_chart': create_jobs_chart(df_filtered),
    'ghg_methodology': create_ghg_methodology_chart(df_filtered),
    'ghg_timeline': create_ghg_charts(df_filtered),
    'key_objectives': create_key_objectives_by_project_type_chart(df_filtered),
    'key_objectives_lollipop': create_key_objectives_lollipop_chart(df_filtered)
  }