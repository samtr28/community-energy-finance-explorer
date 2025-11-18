import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from .Global_Server_Functions import get_data
from .config import COLOUR_MAPPING, gradient_palette, dunsparce_colors
import plotly.express as px
import ast

DATA = get_data()

@anvil.server.callable
def build_province_pie():
  cols = ["province", "province_abbr"]
  df = DATA.loc[:, cols].copy()
  fig = px.pie(df, names='province_abbr', hole=0.3)
  fig.update_traces(
    textposition='inside', 
    textinfo='percent+label',
    hovertemplate='%{label}<extra></extra>'
  )
  return fig
  
@anvil.server.callable
def get_summary_data():
  total_cost = DATA['total_cost'].sum()
  row_count = len(DATA)

  return total_cost, row_count


@anvil.server.callable
def create_capital_flow_overview():
  """
  Creates a basic Sankey diagram showing capital flow from category to project type.
  No filters - shows all data.
  
  Returns:
  plotly.graph_objects.Figure: Sankey diagram figure
  """
  # Process all data (no filters)
  rows = []
  for idx, row in DATA.iterrows():
    capital_mix = row['capital_mix']
    if isinstance(capital_mix, str):
      capital_mix = ast.literal_eval(capital_mix)
    if not capital_mix:
      continue

    for item in capital_mix:
      rows.append({
        'category': item['category'],
        'amount': item['amount'],
        'project_type': row.get('project_type'),
      })

  df_long = pd.DataFrame(rows)
  df_long['project_type'] = df_long['project_type'].apply(ast.literal_eval)
  df_long['count'] = df_long['project_type'].apply(len)
  df_long = df_long.explode('project_type').reset_index(drop=True)
  df_long['amount'] = df_long['amount'] / df_long['count']
  df_long = df_long.drop('count', axis=1)

  # Build node lists
  categories_list = list(df_long['category'].unique())
  project_types_list = list(df_long['project_type'].unique())
  all_nodes = categories_list + project_types_list

  # Aggregate flows from category to project type
  agg_c2p = df_long.groupby(['category', 'project_type'])['amount'].sum().reset_index()

  # Build flow lists
  sources = list(agg_c2p['category'].map(lambda x: all_nodes.index(x)))
  targets = list(agg_c2p['project_type'].map(lambda x: all_nodes.index(x)))
  values = list(agg_c2p['amount'])

  # Node colors
  node_colors = []
  for node in all_nodes:
    if node in categories_list:
      node_colors.append(COLOUR_MAPPING.get(node, '#808080'))
    else:  # Project types
      node_colors.append('#696969')

  # Link colors (transparent versions of category colors)
  def make_transparent(color):
    if color.startswith('#'):
      r = int(color[1:3], 16)
      g = int(color[3:5], 16)
      b = int(color[5:7], 16)
      return f'rgba({r}, {g}, {b}, 0.3)'
    return color

  link_colors = []
  for _, row in agg_c2p.iterrows():
    link_colors.append(make_transparent(COLOUR_MAPPING.get(row['category'], '#808080')))

