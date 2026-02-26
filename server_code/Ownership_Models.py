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

# ==================== UTILITY FUNCTIONS ====================

def wrap_text(text, width=15):
  """Wrap text to specified width for better display in visualizations"""
  return '<br>'.join(textwrap.wrap(str(text), width=width))

def get_contrast_color(hex_color):
  """
  Determine if white or black text should be used on a given background color.
  Returns 'white' or 'black' based on luminance calculation.
  """
  if not hex_color or not hex_color.startswith('#'):
    return 'white'

  # Remove '#' and convert to RGB
  hex_color = hex_color.lstrip('#')
  r = int(hex_color[0:2], 16)
  g = int(hex_color[2:4], 16)
  b = int(hex_color[4:6], 16)

  # Calculate relative luminance
  luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

  # Return black for light backgrounds, white for dark
  return 'black' if luminance > 0.5 else 'white'

# ==================== OWNERSHIP DATA PROCESSING ====================

def process_owners_data(df):
  """
  Convert a dataframe with owners column into a long-format dataframe.
  Each row represents one owner with their details.
  """
  rows = []
  for idx, row in df.iterrows():
    owners = row.get('owners', [])
    if not owners:
      continue

    for owner in owners:
      rows.append({
        'record_id': row.get('record_id'),
        'owner_name': owner.get('owner_name'),
        'owner_type': owner.get('owner_type'),
        'owner_percent': owner.get('owner_percent'),
        'project_type': row.get('project_type'),
        'project_name': row.get('project_name'),
        'province': row.get('province'),
        'project_scale': row.get('project_scale'),
        'stage': row.get('stage'),
        'indigenous_ownership': row.get('indigenous_ownership'),
        'total_cost': row.get('total_cost'),
      })

  df_owners_long = pd.DataFrame(rows)

  return df_owners_long

def apply_filters(df, provinces=None, proj_types=None, stages=None, 
                  indigenous_ownership=None, project_scale=None):
  """
  Apply filters to ownership dataframe. Returns filtered copy.
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

# ==================== OWNERSHIP CHART CREATION FUNCTIONS ====================

def create_ownership_treemap_internal(df_owners):
  """
    Create treemap with toggle showing ownership composition by owner type.
    Two views: By Capital Value and By Project Count.
    """
  if df_owners.empty:
    fig = go.Figure()
    fig.update_layout(title='No ownership data available for selected filters')
    return fig

    # Calculate project count data
  project_data = df_owners.groupby('owner_type')['owner_percent'].sum().reset_index()
  project_data['percentage'] = (project_data['owner_percent'] / project_data['owner_percent'].sum()) * 100

  # Calculate capital value data
  df_owners_copy = df_owners.copy()
  df_owners_copy['ownership_value'] = (df_owners_copy['owner_percent'] / 100) * df_owners_copy['total_cost']
  value_data = df_owners_copy.groupby('owner_type')['ownership_value'].sum().reset_index()
  value_data['percentage'] = (value_data['ownership_value'] / value_data['ownership_value'].sum()) * 100

  # Get consistent colors
  colors = get_owner_type_colors(df_owners['owner_type'].unique(), palette=dunsparce_colors)

  # Helper function to create treemap trace
  def make_treemap(data, value_col, visible=True):
    labels = data['owner_type'].apply(lambda x: wrap_text(x, width=20))
    return go.Treemap(
      labels=labels,
      parents=[''] * len(data),
      values=data[value_col],
      textinfo='label+percent parent',
      textfont=dict(size=12, family='Arial, sans-serif'),
      customdata=list(zip(data['owner_type'], data['percentage'])),
      hovertemplate='<b>%{customdata[0]}</b><br>%{customdata[1]:.1f}%<extra></extra>',
      visible=visible,
      marker=dict(
        colors=[colors[ot] for ot in data['owner_type']],
        line=dict(width=2, color='white')
      )
    )

    # Create figure with both traces (value first, project second)
  fig = go.Figure()
  fig.add_trace(make_treemap(value_data, 'ownership_value', visible=True))
  fig.add_trace(make_treemap(project_data, 'owner_percent', visible=False))

  # Title configuration
  title_config = {
    'text': 'Ownership composition of community energy projects',
    'x': 0,
    'xanchor': 'left'
  }

  # Layout with toggle buttons (capital value first, project count second)
  fig.update_layout(
    title=title_config,
    updatemenus=[dict(
      type='buttons',
      direction='left',
      buttons=[
        dict(
          label='By Dollar Amount',
          method='update',
          args=[{'visible': [True, False]}, {'title': title_config}]
        ),
        dict(
          label='By Project Count',
          method='update',
          args=[{'visible': [False, True]}, {'title': title_config}]
        )
      ],
      pad={'r': 10, 't': 10},
      showactive=True,
      x=0.5, y=1.07,
      xanchor='left', yanchor='top',
      bgcolor='rgba(255, 255, 255, 0.8)',
      bordercolor='gray',
      borderwidth=1
    )],
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    margin=dict(t=0, b=0, l=0, r=0)
  )

  return fig

def create_ownership_scale_pies_internal(df_owners):
  """Create pie charts showing ownership composition by project scale."""
  scale_order = [
    "Micro (< $100K)", 
    "Small ($100K-$1M)", 
    "Medium ($1M-$5M)", 
    "Large ($5M-$25M)", 
    "Very Large ($25M-$100M)",
    "Mega (> $100M)"
  ]
  scales_in_data = [s for s in scale_order if s in df_owners['project_scale'].values]
  if not scales_in_data:
    fig = go.Figure()
    fig.update_layout(title='No data available for selected filters')
    return fig
  owner_type_colors = get_owner_type_colors(df_owners['owner_type'].unique(), palette=dunsparce_colors)
  fig = make_subplots(
    rows=1, 
    cols=len(scales_in_data),
    specs=[[{'type': 'domain'}] * len(scales_in_data)]
  )
  for i, scale in enumerate(scales_in_data):
    sub = df_owners[df_owners['project_scale'] == scale]
    grouped = sub.groupby('owner_type', as_index=False)['owner_percent'].sum()
    n = sub['record_id'].nunique()

    # Calculate percentages for threshold
    total = grouped['owner_percent'].sum()
    grouped['percentage'] = (grouped['owner_percent'] / total) * 100

    # Only show text if slice is >= 5%
    threshold = 5
    grouped['text_display'] = grouped['percentage'].apply(
      lambda x: f'{x:.1f}%' if x >= threshold else ''
    )

    fig.add_trace(
      go.Pie(
        labels=grouped['owner_type'], 
        values=grouped['owner_percent'], 
        title=dict(
          text=f"{scale}<br>({n} projects)<br> ",
          font=dict(size=11, color='black', family='Arial, sans-serif'),
          position='top center'
        ),
        marker=dict(colors=[owner_type_colors[ot] for ot in grouped['owner_type']]),
        sort=False,
        textinfo='text',
        text=grouped['text_display'],
        textfont=dict(size=10, family='Arial, sans-serif'),
        hovertemplate='<b>%{label}</b><br>%{percent}<extra></extra>'
      ),
      row=1, col=i+1
    )
  fig.update_layout(
    title={
      'text': 'Ownership composition by project scale', 
      'x': 0, 
      'xanchor': 'left',
      'y': 0.95,
      'yanchor': 'top'
    },
    showlegend=False,
    margin=dict(t=0, b=0, l=0, r=0),
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(size=12, color='black', family='Arial, sans-serif')
  )
  return fig

def create_indigenous_ownership_stacked_internal(df_owners):
  """Create single stacked bar showing Indigenous ownership distribution."""
  if df_owners.empty:
    fig = go.Figure()
    fig.update_layout(title='No data available for selected filters')
    return fig

  ownership_counts = df_owners.groupby('indigenous_ownership')['record_id'].nunique().reset_index()
  ownership_counts.columns = ['Category', 'Count']

  # Calculate percentages
  total = ownership_counts['Count'].sum()
  ownership_counts['Percentage'] = (ownership_counts['Count'] / total) * 100

  # Sort by meaningful order (reversed)
  order = [
    'Not sure',
    'No Indigenous ownership',
    'Minority Indigenous owned (1-49%)',
    'Half Indigenous owned (50%)',
    'Majority Indigenous owned (51-99%)',
    'Wholly Indigenous owned (100%)'
  ]
  ownership_counts['Category'] = pd.Categorical(ownership_counts['Category'], categories=order, ordered=True)
  ownership_counts = ownership_counts.sort_values('Category').reset_index(drop=True)

  # Use every second color from gradient palette, reversed
  colors = [gradient_palette[i*2] for i in range(len(ownership_counts))][::-1]

  fig = go.Figure()

  for i, row in ownership_counts.iterrows():
    fig.add_trace(go.Bar(
      x=[''],
      y=[row['Count']],
      name=row['Category'],
      orientation='v',
      text=f"<b>{row['Percentage']:.1f}%  -  {row['Category']}</b>",
      textposition='inside',
      textfont=dict(size=11),
      marker=dict(color=colors[i]),
      hovertemplate=f"<b>{row['Category']}</b><br>Projects: {row['Count']}<br>{row['Percentage']:.1f}%<extra></extra>"
    ))

  fig.update_layout(
    title={'text': 'Indigenous project ownership', 'x': 0, 'xanchor': 'left'},
    barmode='stack',
    showlegend=False,
    xaxis=dict(visible=False),
    yaxis=dict(visible=False),
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    margin=dict(t=40, b=0, l=0, r=0),
  )

  return fig

def create_bottleneck_lollipop_internal(df):
  """
    Create lollipop chart showing top financing bottlenecks.
    Displays horizontal lines with dots at the end showing count values.
    Only shows pre-selected key bottlenecks.
    Uses dunsparce_colors[12] for the lollipop color.
    """
  from plotly.subplots import make_subplots

  # Define which bottlenecks to keep
  keep = [
    "Challenges with project governance or decision-making",
    "Conflicts among stakeholders or partners",
    "Limited community engagement or support",
  ]

  # Count bottleneck occurrences
  bottleneck_counts = df['bottlenecks'].explode().value_counts().reset_index()
  bottleneck_counts.columns = ['bottleneck', 'count']

  # Filter to only keep specified bottlenecks
  bottleneck_counts = bottleneck_counts[bottleneck_counts['bottleneck'].isin(keep)]

  # Sort by count descending
  bottleneck_counts = bottleneck_counts.sort_values('count', ascending=True)

  # Prepare data
  bottlenecks = bottleneck_counts['bottleneck'].tolist()
  counts = bottleneck_counts['count'].tolist()
  y_pos = list(range(len(bottlenecks)))

  # Create subplot
  fig = make_subplots()

  # Calculate a fixed x position for all labels
  label_x_position = 0

  # Use color from dunsparce palette - index 12
  lollipop_color = dunsparce_colors[11]


  # Add lines and annotations for each bottleneck
  for i, b in enumerate(bottlenecks):
    # Add line from 0 to count value
    fig.add_scatter(
      x=[0, counts[i]], 
      y=[i, i],
      mode="lines", 
      line=dict(color=lollipop_color, width=6), 
      showlegend=False,
      hoverinfo='skip'
    )

    # Add bottleneck label at fixed position
    fig.add_annotation(
      text=bottlenecks[i], 
      x=label_x_position,
      y=i+0.37, 
      xanchor="left",
      yanchor="middle",
      showarrow=False,
      font=dict(family='Arial, sans-serif', size=13, color='#392000')
    )

    # Add count value on the dot - BIGGER, BOLD, WHITE
    fig.add_annotation(
      text=f'<b>{counts[i]}</b>',  # Use HTML bold tag
      x=counts[i], 
      y=i, 
      xanchor="center",
      yanchor="middle",
      showarrow=False,
      font=dict(color='white', family='Arial, sans-serif', size=16)
    )

  # Add dots at the end of each line
  fig.add_scatter(
    x=counts, 
    y=y_pos, 
    mode="markers", 
    marker=dict(size=30, color=lollipop_color),
    showlegend=False,
    hovertemplate='<b>%{text}</b><br>Count: %{x}<extra></extra>',
    text=bottlenecks
  )

  # Update axes
  fig.update_xaxes(
    visible=False,
    range=[0, max(counts)*1.15] if counts else [0, 10], 
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
    font=dict(family='Arial, sans-serif', size=12, color='#392000'),
    margin=dict(l=0, r=0, t=35, b=0),
    title={
      'text': 'Ownership Bottlenecks',
      'font': {'family': 'Arial, sans-serif', 'size': 16, 'color': '#392000'},
      'x': 0.01,
      'xanchor': 'left',
      'y': 0.98,
      'yanchor': 'top'
    }
  )

  return fig

def create_ownership_financing_funnel_internal(df):
  """Create funnel chart showing top 10 ownership-financing combinations."""
  if df.empty:
    fig = go.Figure()
    fig.update_layout(title='No data available for selected filters')
    return fig
  # Extract owner-finance pairs
  pairs = []
  for _, row in df.iterrows():
    owners = row.get('owners', [])
    financing = row.get('financing_mech', [])
    if not owners or not financing:
      continue
    # Create all combinations
    for o in owners:
      for f in financing:
        pairs.append({
          'Owner': o.get('owner_type', 'Unknown'),
          'Finance': f.get('category', 'Unknown')
        })
  if not pairs:
    fig = go.Figure()
    fig.update_layout(title='No ownership-financing data available')
    return fig
  pairs_df = pd.DataFrame(pairs)
  # Count combinations and get top 10
  combo_counts = pairs_df.groupby(['Owner', 'Finance']).size().reset_index(name='Count')
  combo_counts['Label'] = combo_counts['Owner'] + ' → ' + combo_counts['Finance']
  combo_counts = combo_counts.sort_values('Count', ascending=False).head(10)

  # Wrap labels for better readability
  combo_counts['Label_wrapped'] = combo_counts['Label'].apply(lambda x: wrap_text(x, width=50))

  # Wrap labels for better readability
  combo_counts['Label_wrapped'] = combo_counts['Label'].apply(lambda x: wrap_text(x, width=50))
  # Create funnel chart
  fig = go.Figure(go.Funnel(
    y=combo_counts['Label_wrapped'],
    x=combo_counts['Count'],
    textposition="inside",
    textfont=dict(size=12, family='Arial, sans-serif'),
    marker=dict(
      color=gradient_palette[:len(combo_counts)],
      line=dict(width=0)  # Remove bar borders
    ),
    customdata=combo_counts['Label'],
    hovertemplate='<b>%{customdata}</b><br>Count: %{x}<extra></extra>'
  ))

  # Add horizontal lines under each label
  shapes = []
  for i in range(len(combo_counts)):
    shapes.append(
      dict(
        type='line',
        xref='paper',
        yref='y',
        x0=-1.5,
        x1=0,  # Adjust this to control line length (0-1, where 1 is full width)
        y0=i - 0.45,  # Position below each label
        y1=i - 0.45,
        line=dict(color='#cccccc', width=1)
      )
    )

  # Add horizontal lines under each label
  shapes = []
  for i in range(len(combo_counts)):
    shapes.append(
      dict(
        type='line',
        xref='paper',
        yref='y',
        x0=-1.5,
        x1=0,
        y0=i - 0.45,
        y1=i - 0.45,
        line=dict(color='#cccccc', width=1)
      )
    )
  fig.update_layout(
    title={'text': 'Top 10 Ownership-Financing Combinations', 'x': 0, 'xanchor': 'left'},
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    margin=dict(t=50, b=30, l=20, r=30),
    yaxis=dict(side='left'),
    shapes=shapes  # Add the divider lines
  )
  return fig


# ==================== MAIN OWNERSHIP CALLABLE FUNCTION ====================

@anvil.server.callable
def get_all_ownership_charts(provinces=None, proj_types=None, stages=None,
                             indigenous_ownership=None, project_scale=None):
  """
  Single server call that returns ALL ownership chart figures at once.
  """
  # Loa raw data ONCE
  df_raw = get_data()
  
  
  # Apply filters to raw data (for box plot, bottlenecks, AND treemap)
  df_raw_filtered = apply_filters(df_raw, provinces, proj_types, stages, 
                                  indigenous_ownership, project_scale)


  # Process owners data ONCE
  df_owners = process_owners_data(df_raw)


  # Apply filters to owners data
  df_owners_filtered = apply_filters(
    df_owners, 
    provinces, 
    proj_types, 
    stages, 
    indigenous_ownership, 
    project_scale
  )

  # Add this block:
  if df_owners_filtered.empty:
    empty_fig = go.Figure()
    empty_fig.update_layout(title="No data available for selected filters")
    return {
      'ownership_treemap': empty_fig,
      'scale_pies': empty_fig,
      'indigenous_pie': empty_fig,
      'lollipop_chart': empty_fig,
      'funnel_chart': empty_fig
    }

  results = {
    'ownership_treemap': create_ownership_treemap_internal(df_owners_filtered),
    'scale_pies': create_ownership_scale_pies_internal(df_owners_filtered),
    'indigenous_pie': create_indigenous_ownership_stacked_internal(df_owners_filtered),
    'lollipop_chart': create_bottleneck_lollipop_internal(df_raw_filtered),
    'funnel_chart': create_ownership_financing_funnel_internal(df_raw_filtered)
  }

  return results
