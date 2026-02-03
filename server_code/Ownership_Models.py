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
# Option 2: Temporarily set options for one print
  with pd.option_context('display.max_columns', None, 'display.width', None):
    print(df_owners_long.head(5))
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
    Two views: By Project Count and By Capital Value.
    """
  if df_owners.empty:
    fig = go.Figure()
    fig.update_layout(title='No ownership data available')
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
      textfont=dict(size=12,),
      customdata=list(zip(data['owner_type'], data['percentage'])),
      hovertemplate='<b>%{customdata[0]}</b><br>%{customdata[1]:.1f}%<extra></extra>',
      visible=visible,
      marker=dict(
        colors=[colors[ot] for ot in data['owner_type']],
        line=dict(width=2, color='white')
      )
    )

    # Create figure with both traces
  fig = go.Figure()
  fig.add_trace(make_treemap(project_data, 'owner_percent', visible=True))
  fig.add_trace(make_treemap(value_data, 'ownership_value', visible=False))

  # Annotations
  annotations = {
    'project': 'Answers: "Which owner types participate in the most projects?"<br>Each project counts equally.',
    'value': 'Answers: "Which owner types control the most capital?"<br>Weighted by each project\'s total cost.'
  }

  def make_annotation(text):
    return dict(
      text=text, showarrow=False, xref='paper', yref='paper',
      x=0.5, y=-0.05, xanchor='center', yanchor='top',
      font=dict(size=10, color='black', family='Arial')
    )

    # Title configuration
  title_config = {
    'text': 'Ownership composition of community energy projects',
    'x': 0,
    'xanchor': 'left'
  }

  # Layout with toggle buttons
  fig.update_layout(
    title=title_config,
    annotations=[make_annotation(annotations['project'])],
    updatemenus=[dict(
      type='buttons',
      direction='left',
      buttons=[
        dict(
          label='By Project Count',
          method='update',
          args=[{'visible': [True, False]}, 
                {'title': title_config, 'annotations': [make_annotation(annotations['project'])]}]
        ),
        dict(
          label='By Capital Value',
          method='update',
          args=[{'visible': [False, True]}, 
                {'title': title_config, 'annotations': [make_annotation(annotations['value'])]}]
        )
      ],
      pad={'r': 10, 't': 10},
      showactive=True,
      x=0.01, y=1.07,
      xanchor='left', yanchor='top',
      bgcolor='rgba(255, 255, 255, 0.8)',
      bordercolor='gray',
      borderwidth=1
    )],
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    margin=dict(t=90, b=55, l=0, r=0)
  )

  return fig

def create_ownership_scale_pies_internal(df_owners):
  """
  Create pie charts showing ownership composition by project scale.
  One pie chart per scale, showing breakdown by owner type.
  """
  # Define project scale order
  scale_order = [
    "Micro (< $100K)", 
    "Small ($100K-$1M)", 
    "Medium ($1M-$5M)", 
    "Large ($5M-$25M)", 
    "Very Large ($25M-$100M)",
    "Mega (> $100M)"
  ]

  # Filter to only scales present in data
  scales_in_data = [s for s in scale_order if s in df_owners['project_scale'].values]

  if not scales_in_data:
    fig = go.Figure()
    fig.update_layout(title='No data available')
    return fig

  # Create consistent color mapping for owner types using dunsparce palette
  all_owner_types = df_owners['owner_type'].unique()
  owner_type_color_map = get_owner_type_colors(all_owner_types, palette='dunsparce')

  # Create one-row figure with a pie per scale
  fig = make_subplots(
    rows=1, 
    cols=len(scales_in_data),
    specs=[[{'type': 'domain'}] * len(scales_in_data)],
    subplot_titles=list(scales_in_data)
  )

  # Add a pie for each project scale
  for i, scale in enumerate(scales_in_data):
    # Filter to this scale
    sub = df_owners[df_owners['project_scale'] == scale]

    # Group by owner type and sum ownership percentages
    grouped = sub.groupby('owner_type', as_index=False)['owner_percent'].sum()

    # Get colors for this scale's owner types
    colors = [owner_type_color_map[ot] for ot in grouped['owner_type']]

    fig.add_trace(
      go.Pie(
        labels=grouped['owner_type'], 
        values=grouped['owner_percent'], 
        name=scale,
        marker=dict(colors=colors),
        sort=False,
        showlegend=(i == 0),  # Only show legend for first pie
        textinfo='percent',
        texttemplate='%{percent:.1%}',
        textfont=dict(size=10,),
        hovertemplate='<b>%{label}</b><br>%{value:.1f}%<extra></extra>'
      ),
      row=1, col=i+1
    )

  # Annotate each subplot with unique project counts
  for i, scale in enumerate(scales_in_data):
    n = df_owners.loc[df_owners['project_scale'] == scale, 'record_id'].nunique()
    fig.layout.annotations[i]['text'] = f"{scale}<br>({n} projects)"
    fig.layout.annotations[i]['font'] = dict(family='Arial, sans-serif', size=10, color='black')

  # Update layout
  fig.update_layout(
    title={
      'text': 'Ownership composition by project scale',
      'font': {'family': 'Arial, sans-serif', 'size': 16, 'color': 'black'},
      'x': 0,
      'xanchor': 'left',
      'y': 0.98,
      'yanchor': 'top'
    },
    showlegend=True,
    legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
    margin=dict(t=0, b=35, l=0, r=0),
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(family='Arial, sans-serif', size=12, color='black')
  )

  return fig

# ==================== MAIN OWNERSHIP CALLABLE FUNCTION ====================

@anvil.server.callable
def get_all_ownership_charts(provinces=None, proj_types=None, stages=None,
                             indigenous_ownership=None, project_scale=None):
  """
  Single server call that returns ALL ownership chart figures at once.
  """
  # DEBUG: Print what filters were received
  print("=== FILTER DEBUG ===")
  print(f"provinces: {provinces} (type: {type(provinces)})")
  print(f"proj_types: {proj_types} (type: {type(proj_types)})")
  print(f"stages: {stages} (type: {type(stages)})")
  print(f"indigenous_ownership: {indigenous_ownership} (type: {type(indigenous_ownership)})")
  print(f"project_scale: {project_scale} (type: {type(project_scale)})")

  # Load raw data ONCE
  df_raw = get_data()

  # Process owners data ONCE
  df_owners = process_owners_data(df_raw)
  print(f'Data processed: {len(df_owners)} total rows')

  # DEBUG: Show sample of data before filtering
  print("Sample before filtering:")
  print(df_owners[['province', 'project_type', 'stage', 'project_scale']].head(3))

  # Apply filters to owners data
  df_owners_filtered = apply_filters(
    df_owners, 
    provinces, 
    proj_types, 
    stages, 
    indigenous_ownership, 
    project_scale
  )

  print(f'After filtering: {len(df_owners_filtered)} rows')

    # Add this block:
  if df_owners_filtered.empty:
    print("WARNING: No ownership data after filtering")
    empty_fig = go.Figure()
    empty_fig.update_layout(title="No data available for selected filters")
    return {
      'ownership_treemap': empty_fig,
      'scale_pies': empty_fig,
    }
    
  results = {
    'ownership_treemap': create_ownership_treemap_internal(df_owners_filtered),
    'scale_pies': create_ownership_scale_pies_internal(df_owners_filtered),
  }


  return results