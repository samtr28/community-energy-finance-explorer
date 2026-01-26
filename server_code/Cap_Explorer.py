import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import pandas as pd
import numpy as np
from .config import COLOUR_MAPPING, gradient_palette, dunsparce_colors
from .Global_Server_Functions import get_data
import plotly.graph_objects as go
import plotly.express as px
import textwrap

# ==================== UTILITY FUNCTIONS ====================

def wrap_text(text, width=15):
  """Wrap text to specified width for better display in visualizations"""
  return '<br>'.join(textwrap.wrap(text, width=width))

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

def standardize_category_name(category):
  """Standardize category names to be consistent across all charts"""
  if not category:
    return category

  category_lower = str(category).lower()

  if 'debt' in category_lower:
    return 'Debt financing'
  elif 'grant' in category_lower:
    return 'Grants & non-repayable contributions'
  elif 'crowdfund' in category_lower or 'crowd fund' in category_lower:
    return 'Crowdfunding'
  elif 'internal' in category_lower:
    return 'Internal capital'
  elif 'equity' in category_lower:
    return 'External equity investments'
  elif 'community' in category_lower:
    return 'Community financing'
  else:
    return category

def apply_filters(df, provinces=None, proj_types=None, stages=None, indigenous_ownership=None, project_scale=None):
  """
    Apply filters to dataframe. Returns filtered copy.
    Handles filtering by province, project type, stage, indigenous ownership, and project scale.
    """
  # *** ADD THIS: Handle already-empty input ***
  if df.empty:
    return df
    
  df = df.copy()

  if provinces:
    df = df[df["province"].isin(provinces)]

  if proj_types:
    df = df[df["project_type"].apply(lambda lst: any(t in lst for t in proj_types))]

  if stages:
    df = df[df["stage"].isin(stages)]

  if indigenous_ownership:
    df = df[df["indigenous_ownership"].isin(indigenous_ownership)]

  if project_scale:
    df = df[df["project_scale"].isin(project_scale)]

  return df

# ==================== DATA PROCESSING ====================

def process_capital_mix_data(df):
  """
    Convert a dataframe with capital_mix and debt columns into a long-format
    dataframe with cleaned time and source columns, merged debt repayment/interest info.
    Assumes capital_mix and debt are already Python objects (lists of dicts).
    
    Steps:
    1. Explode capital_mix into long format
    2. Explode debt info
    3. Merge debt info into capital_mix
    4. Clean time columns
    5. Convert time strings to numeric
    6. Normalize source values
    """
  # Step 1: Explode capital_mix into long format
  rows = []
  for _, row in df.iterrows():
    capital_mix = row.get('capital_mix', [])
    if not capital_mix:
      continue
    for item in capital_mix:
      rows.append({
        'record_id': row.get('record_id'),
        'total_cost': row.get('total_cost'),
        'name': item.get('name'),
        'source': item.get('source'),
        'category': item.get('category'),
        'item_type': item.get('item_type'),
        'amount': item.get('amount'),
        'project_type': row.get('project_type'),
        'stage': row.get('stage'),
        'province': row.get('province'),
        'project_scale': row.get('project_scale'),
        'grants_time': row.get('grants_time'),
        'debt_time': row.get('debt_time'),
        'equity_time': row.get('equity_time'),
        'community_time': row.get('community_finance_time'),
        'crowdfunding_time': row.get('crowdfunding_time'),
        'indigenous_ownership': row.get('indigenous_ownership'),
        'all_financing_mechanisms': row.get('all_financing_mechanisms')
      })
  df_long = pd.DataFrame(rows)

  #accoutnt for if there is no data 
  if df_long.empty:
    return pd.DataFrame(columns=[
      'record_id', 'total_cost', 'name', 'source', 'category', 
      'item_type', 'amount', 'project_type', 'stage', 'province',
      'project_scale', 'indigenous_ownership', 'all_financing_mechanisms',
      'time_to_funding'
    ])

  # Step 2: Explode debt info
  debt_rows = []
  for _, row in df.iterrows():
    debt_list = row.get('debt', [])
    if not debt_list:
      continue
    for item in debt_list:
      debt_rows.append({
        'record_id': row.get('record_id'),
        'total_cost': row.get('total_cost'),
        'name': item.get('debt_name'),
        'source': item.get('debt_source'),
        'debt_interest': item.get('debt_interest'),
        'repayment_period': item.get('debt_repayment'),
      })
  df_debt = pd.DataFrame(debt_rows)

  # Step 3: Merge debt info into capital_mix long dataframe
  df_long = pd.merge(
    df_long,
    df_debt,
    on=['record_id', 'total_cost', 'name', 'source'],
    how='left'
  )

  # Step 4: Clean time columns
  time_columns = ['grants_time', 'debt_time', 'equity_time', 'community_time', 'crowdfunding_time']
  for col, cat in zip(time_columns, ['Grants','Debt','Equity','Community finance','Crowdfund']):
    df_long.loc[(df_long['category'] != cat) & (df_long[col].notnull()), col] = pd.NaT

    # Step 5: Convert time strings to numeric
  def time_to_numeric(time_str):
    if pd.isna(time_str) or time_str == 'Missing value':
      return np.nan
    elif time_str == 'Less than 1 year':
      return 0.5
    elif time_str == '2-3 years':
      return 2.5
    elif time_str == '4-5 years':
      return 4.5
    elif time_str == '8-10 years':
      return 9.0
    else:
      return np.nan

  df_long['time_to_funding'] = df_long.apply(
    lambda row: next(
      (time_to_numeric(row[col]) for col in time_columns if pd.notna(row[col])),
      np.nan
    ),
    axis=1
  )
  df_long = df_long.drop(columns=time_columns)

  # Step 6: Normalize source values
  df_long['source'] = df_long['source'].replace({
    'Other': 'Other/Unknown',
    'Not sure': 'Other/Unknown',
    'Aggregate total': 'Other/Unknown',
    'Aggregate Total': 'Other/Unknown',
    "Don't know": 'Other/Unknown',
  })
  df_long.loc[df_long['source'] == 'Other/Unknown', 'source'] = df_long['source'] + '-' + df_long['category']

  # Standardize category names
  df_long['category'] = df_long['category'].apply(standardize_category_name)

  return df_long

def get_category_order(df):
  """
    Calculate category order based on average time to funding (smallest to largest).
    This is the master ordering used by all charts.
    Internal capital is excluded from this calculation.
    """
  # *** ADD THIS: Return default order if empty ***
  if df.empty or 'category' not in df.columns or 'time_to_funding' not in df.columns:
    return [
      'Grants & non-repayable contributions',
      'Crowdfunding',
      'Community financing',
      'External equity investments',
      'Debt financing'
    ]
    
  # Drop internal capital
  df_no_internal = df[df['category'] != 'Internal capital']

  # Calculate average time to funding by category
  averages = df_no_internal.groupby('category')['time_to_funding'].mean()

  # Sort ascending (smallest to largest)
  averages = averages.sort_values(ascending=True)

  return averages.index.tolist()

# ==================== MAIN CALLABLE FUNCTION ====================

@anvil.server.callable
def get_all_capital_charts(provinces=None, proj_types=None, stages=None,
                           indigenous_ownership=None, project_scale=None):
  """
  Single server call that returns ALL chart figures and indicators at once.
  """
  print("Loading data for all charts...")

  # Load raw data ONCE
  df_raw = get_data()

  # Process capital mix data ONCE
  df_capital_mix = process_capital_mix_data(df_raw)

  # Apply filters to raw data (for box plot, bottlenecks, AND treemap)
  df_raw_filtered = apply_filters(df_raw, provinces, proj_types, stages, 
                                  indigenous_ownership, project_scale)

  # For capital mix: apply ALL filters including project_type
  df_capital_filtered_with_proj = apply_filters(df_capital_mix, provinces, proj_types, stages,
                                                indigenous_ownership, project_scale)

  # For Sankey: apply filters EXCEPT project_type
  df_capital_filtered_no_proj = apply_filters(df_capital_mix, provinces, None, stages,
                                              indigenous_ownership, project_scale)

  # *** ADD THIS BLOCK: Check for empty data ***
  if df_capital_filtered_with_proj.empty:
    print("WARNING: No data after filtering")
    empty_fig = go.Figure()
    empty_fig.update_layout(title="No data available for selected filters")

    return {
      'box_plot': empty_fig,
      'sankey': empty_fig,
      'time_chart': empty_fig,
      'stacked_bar': empty_fig,
      'bottleneck_chart': empty_fig,
      'treemap': empty_fig,
      'scale_pies': empty_fig,
      'indicators': {
        'equity': {'type': 'N/A', 'source': 'N/A'},
        'debt': {'interest': 'N/A', 'repayment': 'N/A', 'type': 'N/A', 'source': 'N/A'},
        'grants': {'type': 'N/A', 'source': 'N/A'},
        'community_finance': {'type': 'N/A', 'source': 'N/A'},
        'crowdfunding': {'type': 'N/A', 'source': 'N/A'}
      }
    }
  
  # Calculate category order ONCE
  category_order = get_category_order(df_capital_filtered_with_proj)
  category_order_reversed = list(reversed(category_order))

  print("Generating all charts...")

  # Generate ALL charts
  results = {
    'box_plot': create_box_plot_internal(df_raw_filtered, category_order_reversed),
    'sankey': create_sankey_internal(df_capital_filtered_no_proj, proj_types),
    'time_chart': create_time_chart_internal(df_capital_filtered_with_proj, category_order),
    'stacked_bar': create_stacked_bar_internal(df_capital_filtered_with_proj, category_order_reversed),
    'bottleneck_chart': create_bottleneck_lollipop_internal(df_raw_filtered),
    'treemap': create_treemap_internal(df_raw_filtered),
    'scale_pies': create_scale_pies_internal(df_capital_filtered_with_proj),  # NEW CHART
    'indicators': calculate_indicators_internal(df_capital_filtered_with_proj)
  }

  print("All charts generated successfully!")

  return results

# ==================== CHART CREATION FUNCTIONS ====================

def create_box_plot_internal(df, category_order):
  """
    Create box plot showing distribution of project costs by financing category.
    Uses percentage columns from raw data.
    Shows all data points overlaid on boxes.
    """
  relevant_columns = [
    'total_percent_grants', 
    'total_percent_equity',
    'total_percent_debts', 
    'total_percent_internal', 
    'total_percent_community_finance',
    'total_percent_crowdfund'
  ]

  df_relevant = df[relevant_columns]
  df_long = df_relevant.melt(var_name='category', value_name='percent')
  df_long = df_long[df_long['percent'] > 0]

  # Clean up category names
  df_long['category'] = df_long['category'].str.replace('total_percent_', '')
  df_long['category'] = df_long['category'].str.replace('_', ' ')

  # Standardize category names
  df_long['category'] = df_long['category'].apply(standardize_category_name)

  # Filter category_order to only include categories present in data
  filtered_order = [cat for cat in category_order if cat in df_long['category'].values]

  # Get colors from COLOUR_MAPPING
  color_map = {cat: COLOUR_MAPPING.get(cat, '#808080') for cat in df_long['category'].unique()}

  # Create box plot
  fig = px.box(
    df_long, 
    x='category', 
    y='percent', 
    points='all', 
    color='category',
    color_discrete_map=color_map,
    category_orders={'category': filtered_order}
  )

  fig.update_layout(
    showlegend=False,
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    yaxis_title='',
    xaxis_title='',
    xaxis=dict(tickangle=20, tickfont=dict(size=10, color='black', family='Arial, sans-serif'), linecolor='grey', showline=True),
    yaxis=dict(ticksuffix="%", tickfont=dict(color='black', family='Arial, sans-serif'), linecolor='grey', showline=True),
    margin=dict(l=0, r=0, t=35, b=0),
    title={
      'text': 'Average contribution of each financing source to total project costs',
      'font': {'family': 'Arial, sans-serif', 'size': 16, 'color': 'black'},
      'x': 0.01,
      'xanchor': 'left',
      'y': 0.98,
      'yanchor': 'top'
    }
  )

  return fig

def create_time_chart_internal(df, category_order):
  """
    Create horizontal bar chart showing average time to funding by category.
    Excludes Internal capital. Uses category_order for consistent ordering.
    Text labels show category name and time value with automatic color contrast.
    """
  # Drop the 'Internal' category
  df = df[df['category'] != 'Internal capital']
  # Group by funding category and compute mean time_to_funding
  averages = df.groupby('category')['time_to_funding'].mean()
  # Reindex to match the provided order (smallest to largest)
  averages = averages.reindex(category_order)
  # Map colors
  colors = [COLOUR_MAPPING.get(cat, '#808080') for cat in averages.index]

  # Determine text colors based on background
  text_colors = [get_contrast_color(color) for color in colors]

  # Create horizontal bar chart
  fig = go.Figure(data=[go.Bar(
    y=averages.index,
    x=averages.values,
    orientation='h',
    text=[f'{cat}: {val:.1f} years' for cat, val in zip(averages.index, averages.values)],
    textposition='inside',
    textfont=dict(family='Arial, sans-serif'),
    marker=dict(color=colors)
  )])

  # Update text colors individually for each bar
  for i, text_color in enumerate(text_colors):
    fig.data[0].textfont.color = text_colors

  fig.update_layout(
    yaxis_title='',
    xaxis_title='',
    showlegend=False,
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    margin=dict(l=0, r=0, t=35, b=0),
    xaxis=dict(visible=False),
    yaxis=dict(showticklabels=False),
    title={
      'text': 'Average time to funding',
      'font': {'family': 'Arial, sans-serif', 'size': 16, 'color': 'black'},
      'x': 0.05,
      'xanchor': 'left',
      'y': 0.98,
      'yanchor': 'top'
    }
  )
  return fig

def create_sankey_internal(df, proj_types=None):
  """
    Create Sankey diagram showing capital flow: Source → Category → Project type.
    Handles Internal capital separately from other categories.
    Uses transparent colors for links, solid colors for nodes.
    Text is black and bold.
    """
  df = df.copy()

  for col in ['project_type', 'amount', 'category', 'source']:
    if col not in df.columns:
      df[col] = None

  def to_list_like(x):
    if isinstance(x, list):
      return x
    if pd.isna(x):
      return []
    return [x]
  df['project_type'] = df['project_type'].apply(to_list_like)

  df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)

  df['pt_count'] = df['project_type'].apply(len).replace(0, 1)
  df['amount'] = df['amount'] / df['pt_count']

  df = df.explode('project_type').reset_index(drop=True)

  if proj_types:
    df = df[df['project_type'].isin(proj_types)]

  df = df.drop(columns=['pt_count'], errors='ignore')

  df_internal = df[df['category'] == 'Internal capital'].copy()
  df_other = df[df['category'] != 'Internal capital'].copy()

  sources_list = list(df_other['source'].dropna().unique())
  categories_list = list(df_other['category'].dropna().unique())
  project_types_list = list(df['project_type'].dropna().unique())

  all_nodes = []
  for lst in (sources_list, categories_list, ['Internal capital'], project_types_list):
    for item in lst:
      if item not in all_nodes:
        all_nodes.append(item)

  agg_s2c = df_other.groupby(['source', 'category'], dropna=False)['amount'].sum().reset_index()
  agg_c2p = df_other.groupby(['category', 'project_type'], dropna=False)['amount'].sum().reset_index()
  agg_i2p = df_internal.groupby(['project_type'], dropna=False)['amount'].sum().reset_index()

  node_index = {label: i for i, label in enumerate(all_nodes)}

  s_s2c = list(agg_s2c['source'].map(lambda x: node_index.get(x)))
  t_s2c = list(agg_s2c['category'].map(lambda x: node_index.get(x)))
  v_s2c = list(agg_s2c['amount'])

  s_c2p = list(agg_c2p['category'].map(lambda x: node_index.get(x)))
  t_c2p = list(agg_c2p['project_type'].map(lambda x: node_index.get(x)))
  v_c2p = list(agg_c2p['amount'])

  internal_idx = node_index.get('Internal capital')
  s_i2p = [internal_idx] * len(agg_i2p)
  t_i2p = list(agg_i2p['project_type'].map(lambda x: node_index.get(x)))
  v_i2p = list(agg_i2p['amount'])

  sources = s_s2c + s_c2p + s_i2p
  targets = t_s2c + t_c2p + t_i2p
  values = v_s2c + v_c2p + v_i2p

  source_to_category = {}
  if not df_other.empty and 'source' in df_other.columns and 'category' in df_other.columns:
    source_to_category = df_other.groupby('source')['category'].first().to_dict()

  node_colors = []
  for node in all_nodes:
    if node in sources_list:
      node_colors.append(COLOUR_MAPPING.get(source_to_category.get(node), '#808080'))
    elif node in categories_list:
      node_colors.append(COLOUR_MAPPING.get(node, '#808080'))
    elif node == 'Internal capital':
      node_colors.append(COLOUR_MAPPING.get('Internal capital', '#808080'))
    else:
      node_colors.append('#696969')

  def make_transparent(color):
    try:
      if isinstance(color, str) and color.startswith('#') and len(color) == 7:
        r = int(color[1:3], 16); g = int(color[3:5], 16); b = int(color[5:7], 16)
        return f'rgba({r}, {g}, {b}, 0.3)'
    except Exception:
      pass
    return color or 'rgba(128,128,128,0.3)'

  link_colors = []
  for _, r in agg_s2c.iterrows():
    link_colors.append(make_transparent(COLOUR_MAPPING.get(r['category'], '#808080')))
  for _, r in agg_c2p.iterrows():
    link_colors.append(make_transparent(COLOUR_MAPPING.get(r['category'], '#808080')))
  for _ in range(len(agg_i2p)):
    link_colors.append(make_transparent(COLOUR_MAPPING.get('Internal capital', '#808080')))

  combined = list(zip(sources, targets, values, link_colors))
  valid = [(s, t, v, c) for s, t, v, c in combined if s is not None and t is not None and (v is not None and v > 0)]
  if not valid:
    fig = go.Figure()
    fig.update_layout(title='No data for selected filters')
    return fig

  sources_valid, targets_valid, values_valid, link_colors_valid = zip(*valid)

  fig = go.Figure(data=[go.Sankey(
    arrangement='perpendicular',
    node=dict(
      align='center',
      thickness=20,
      line=dict(color="white", width=0),
      label=[str(n) for n in all_nodes],
      color=node_colors,
      hovertemplate='%{label}<br>$%{value:,.0f}<extra></extra>'
    ),
    link=dict(
      source=list(sources_valid),
      target=list(targets_valid),
      value=list(values_valid),
      color=list(link_colors_valid),
      hovertemplate='%{source.label} → %{target.label}<br>$%{value:,.0f}<extra></extra>'
    ),
    textfont=dict(color='black', family='Arial, sans-serif', size=12)
  )])

  # Make Sankey text bold and black
  fig.update_traces(textfont=dict(color='black', family='Arial, sans-serif', size=12, weight='bold'))

  fig.update_layout(
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    margin=dict(l=0, r=0, t=35, b=10),
    title={
      'text': 'Capital flow: Source → Category → Project type',
      'font': {'family': 'Arial, sans-serif', 'size': 16, 'color': 'black'},
      'x': 0.01, 'xanchor': 'left', 'y': 0.98, 'yanchor': 'top'
    }
  )

  return fig

def create_stacked_bar_internal(df, category_order):
  """
    Create horizontal stacked bar chart showing funding sources breakdown by category.
    Excludes Internal capital. Generates color shades for sources within each category.
    Shows percentage distribution with labels for segments ≥5%.
    Text color automatically adjusts based on background.
    """
  group_by = 'category'
  stack_by = 'source'

  df = df[df['category'] != 'Internal capital']

  df_grouped = df.groupby([group_by, stack_by])['amount'].sum().reset_index()

  group_totals = df_grouped.groupby(group_by)['amount'].sum().reset_index()
  group_totals.columns = [group_by, 'group_total']
  df_grouped = df_grouped.merge(group_totals, on=group_by)
  df_grouped['percentage'] = (df_grouped['amount'] / df_grouped['group_total']) * 100

  # Use provided category order (filter to only categories in data)
  group_order = [cat for cat in category_order if cat in group_totals[group_by].values]

  def generate_color_shades(hex_color, n_shades):
    if not hex_color or not hex_color.startswith('#'):
      hex_color = '#808080'

    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)

    shades = []
    for i in range(n_shades):
      factor = 0.75 + (0.6 * i / max(n_shades - 1, 1))
      new_r = min(255, int(r * factor))
      new_g = min(255, int(g * factor))
      new_b = min(255, int(b * factor))
      shades.append(f'#{new_r:02x}{new_g:02x}{new_b:02x}')

    return shades

  color_map = {}
  source_order_map = {}

  for group_val in group_order:
    base_color = COLOUR_MAPPING.get(group_val, '#808080')
    group_data = df_grouped[df_grouped[group_by] == group_val].sort_values('amount', ascending=False)
    stack_vals = group_data[stack_by].tolist()

    n_sources = len(stack_vals)
    shades = generate_color_shades(base_color, n_sources)

    for i, stack_val in enumerate(stack_vals):
      key = (group_val, stack_val)
      color_map[key] = shades[i]
      source_order_map[key] = i

  df_grouped['source_order'] = df_grouped.apply(
    lambda row: source_order_map.get((row[group_by], row[stack_by]), 999),
    axis=1
  )

  all_sources = []
  for group_val in group_order:
    group_sources = df_grouped[df_grouped[group_by] == group_val].sort_values('source_order')[stack_by].tolist()
    for src in group_sources:
      if src not in all_sources:
        all_sources.append(src)

  traces = []
  for stack_val in all_sources:
    df_stack = df_grouped[df_grouped[stack_by] == stack_val]

    colors = [color_map.get((row[group_by], stack_val), '#808080') 
              for _, row in df_stack.iterrows()]

    # Determine text color based on background color
    text_colors = [get_contrast_color(color) for color in colors]

    text_labels = [f'{stack_val}: {row["percentage"]:.1f}%' if row["percentage"] >= 5 else '' 
                   for _, row in df_stack.iterrows()]

    # Create individual traces with appropriate text colors
    for idx, (_, row) in enumerate(df_stack.iterrows()):
      if row['percentage'] >= 5:
        traces.append(go.Bar(
          name=stack_val,
          y=[row[group_by]],
          x=[row['percentage']],
          orientation='h',
          text=[text_labels[idx]],
          textposition='inside',
          textfont=dict(size=12, color=text_colors[idx], family='Arial, sans-serif'),
          marker=dict(color=colors[idx]),
          hovertemplate='%{fullData.name}<br>%{x:.1f}%<extra></extra>',
          showlegend=False
        ))
      else:
        traces.append(go.Bar(
          name=stack_val,
          y=[row[group_by]],
          x=[row['percentage']],
          orientation='h',
          text=[''],
          textposition='inside',
          marker=dict(color=colors[idx]),
          hovertemplate='%{fullData.name}<br>%{x:.1f}%<extra></extra>',
          showlegend=False
        ))

  fig = go.Figure(data=traces)

  fig.update_layout(
    barmode='stack',
    showlegend=False,
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(family='Arial, sans-serif', size=12),
    xaxis=dict(visible=False, showticklabels=False),
    yaxis=dict(
      categoryorder='array',
      categoryarray=list(reversed(group_order)),
    ),
    margin=dict(l=0, r=0, t=35, b=0),
    title={
      'text': 'Funding sources by category',
      'font': {'family': 'Arial, sans-serif', 'size': 16, 'color': 'black'},
      'x': 0.01,
      'xanchor': 'left',
      'y': 0.98,
      'yanchor': 'top'
    }
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
    "Difficulty securing up-front capital",
    "Limited access to grants or subsidies",
    "High financing costs",
    "Limited investor interest in community-led projects",
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
  label_x_position = 0.1

  # Use color from dunsparce palette - index 12
  lollipop_color = dunsparce_colors[12]


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
      font=dict(family='Arial, sans-serif', size=14, color=dunsparce_colors[5])
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
    font=dict(family='Arial, sans-serif', size=12, color='#00504a'),
    margin=dict(l=0, r=0, t=35, b=0),
    title={
      'text': 'Financing Bottlenecks',
      'font': {'family': 'Arial, sans-serif', 'size': 16, 'color': '#00504a'},
      'x': 0.01,
      'xanchor': 'left',
      'y': 0.98,
      'yanchor': 'top'
    }
  )

  return fig

def create_treemap_internal(df):
  """
  Create treemap showing usage of financing mechanisms.
  Displays mechanisms grouped by category with size based on count.
  Text wraps with automatic color contrast (white on dark, black on light).
  """

  # *** ADD THIS: Check if input is empty ***
  if df.empty or 'financing_mech' not in df.columns:
    fig = go.Figure()
    fig.update_layout(title='No data available for selected filters')
    return fig

  # Process financing_mech data into long format
  rows = []
  for idx, row in df.iterrows():
    financing_mech = row.get('financing_mech')
    if not financing_mech:
      continue
    for item in financing_mech:
      category = standardize_category_name(item.get('category'))
      source = item.get('source')
      rows.append({
        'record_id': row.get('record_id'),
        'source': source,
        'category': category,
        'count': item.get('count'),
      })

  df_long = pd.DataFrame(rows)

  # *** ADD THIS: Return early if no data ***
  if df_long.empty:
    fig = go.Figure()
    fig.update_layout(title='No financing mechanism data available')
    return fig

  # Normalize source values (like in process_capital_mix_data)
  df_long['source'] = df_long['source'].replace({
    'Other': 'Other/Unknown',
    'Not sure': 'Other/Unknown',
    'Aggregate total': 'Other/Unknown',
    'Aggregate Total': 'Other/Unknown',
    "Don't know": 'Other/Unknown',
  })

  mask = df_long['source'] == 'Other/Unknown'
  df_long.loc[mask, 'source'] = df_long.loc[mask, 'source'] + '-' + df_long.loc[mask, 'category']

  df_grouped = df_long.groupby(['source', 'category']).size().reset_index(name='count')

  # *** ADD THIS: Check grouped data ***
  if df_grouped.empty:
    fig = go.Figure()
    fig.update_layout(title='No financing mechanism data available')
    return fig

  # Build hierarchical structure for go.Treemap
  labels = []
  parents = []
  values = []
  colors = []
  text_colors = []

  # Calculate total counts for each category
  category_totals = df_grouped.groupby('category')['count'].sum().to_dict()

  # Add category level with actual counts
  categories = df_grouped['category'].unique()
  for cat in categories:
    labels.append(cat)
    parents.append("")  # Top level has empty parent
    values.append(category_totals[cat])  # Use actual sum
    cat_color = COLOUR_MAPPING.get(cat, '#808080')
    colors.append(cat_color)
    text_colors.append(get_contrast_color(cat_color))

  # Add source level (children of categories)
  for _, row in df_grouped.iterrows():
    source = row['source']
    category = row['category']
    count = row['count']

    # Wrap text for sources
    wrapped_source = wrap_text(source, width=20) if source else source

    labels.append(wrapped_source)
    parents.append(category)
    values.append(count)

    # Sources inherit category color but slightly lighter
    source_color = COLOUR_MAPPING.get(category, '#808080')
    colors.append(source_color)
    text_colors.append(get_contrast_color(source_color))

  # Create treemap with go.Treemap
  fig = go.Figure(go.Treemap(
    labels=labels,
    parents=parents,
    values=values,
    branchvalues="total",  # Important: parents show their own value plus children
    marker=dict(
      colors=colors,
      line=dict(color='white', width=2)
    ),
    textfont=dict(family='Arial, sans-serif', size=12),
    textposition='middle center',
    hovertemplate='<b>%{label}</b><br>Count: %{value}<extra></extra>'
  ))

  # Apply text colors individually
  fig.data[0].textfont.color = text_colors

  fig.update_layout(
    title={
      'text': 'Use of Funding & Financing Mechanisms',
      'font': {'family': 'Arial, sans-serif', 'size': 16, 'color': 'black'},
      'x': 0.01,
      'xanchor': 'left',
      'y': 0.98,
      'yanchor': 'top'
    },
    font=dict(family='Arial, sans-serif', size=14, color='black'),
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    margin=dict(l=0, r=0, t=35, b=0),
  )

  return fig

# ==================== INDICATORS CALCULATION ====================

def calculate_indicators_internal(df):
  """
    Calculate key indicators for each financing category:
    - Equity: top mechanism type, top source
    - Debt: average interest rate, common repayment period, top mechanism, top source
    - Grants: top mechanism type, top source
    - Community finance: top mechanism type, top source
    - Crowdfunding: top mechanism type, top source
    
    Returns dictionary with category keys containing indicator dictionaries.
    """
  results = {}

  # ========== EQUITY ==========
  eq_df = df[df['category'] == 'Equity financing']
  if len(eq_df) > 0:
    total_projects = eq_df['record_id'].nunique()

    source_counts = eq_df.groupby('source')['record_id'].nunique()
    top_source = source_counts.idxmax()
    top_source_pct = (source_counts.max() / total_projects * 100)

    mechanism_counts = eq_df.groupby('item_type')['record_id'].nunique()
    top_mechanism = mechanism_counts.idxmax() if len(mechanism_counts) > 0 else 'N/A'
    top_mechanism_pct = (mechanism_counts.max() / total_projects * 100) if len(mechanism_counts) > 0 else 0

    results['equity'] = {
      'type': f"{top_mechanism} ({top_mechanism_pct:.0f}% projects)",
      'source': f"{top_source} ({top_source_pct:.0f}% projects)"
    }
  else:
    results['equity'] = {'type': 'N/A', 'source': 'N/A'}

  # ========== DEBT ==========
  debt_df = df[df['category'] == 'Debt financing']
  if len(debt_df) > 0:
    total_projects = debt_df['record_id'].nunique()

    source_counts = debt_df.groupby('source')['record_id'].nunique()
    top_source = source_counts.idxmax()
    top_source_pct = (source_counts.max() / total_projects * 100)

    mechanism_counts = debt_df.groupby('item_type')['record_id'].nunique()
    top_mechanism = mechanism_counts.idxmax()
    top_mechanism_pct = (mechanism_counts.max() / total_projects * 100)

    debt_with_interest = debt_df[debt_df['debt_interest'].notna()].copy()
    if len(debt_with_interest) > 0:
      def extract_avg_rate(rate_str):
        if pd.isna(rate_str):
          return np.nan
        rate_str = str(rate_str).strip().replace('%', '')
        if '-' in rate_str:
          parts = rate_str.split('-')
          try:
            return (float(parts[0].strip()) + float(parts[1].strip())) / 2
          except:
            return np.nan
        else:
          try:
            return float(rate_str)
          except:
            return np.nan

      debt_with_interest['rate_numeric'] = debt_with_interest['debt_interest'].apply(extract_avg_rate)
      valid_rates = debt_with_interest['rate_numeric'].dropna()
      avg_interest = f"{valid_rates.mean():.1f}%" if len(valid_rates) > 0 else 'N/A'
    else:
      avg_interest = 'N/A'

    debt_with_repayment = debt_df[debt_df['repayment_period'].notna()]
    if len(debt_with_repayment) > 0:
      repayment_project_counts = debt_with_repayment.groupby('repayment_period')['record_id'].nunique()
      common_repayment = repayment_project_counts.idxmax()
      repayment_pct = (repayment_project_counts.max() / total_projects * 100)
      repayment_text = f"{common_repayment} ({repayment_pct:.0f}% projects)"
    else:
      repayment_text = 'N/A'

    results['debt'] = {
      'interest': avg_interest,
      'repayment': repayment_text,
      'type': f"{top_mechanism} ({top_mechanism_pct:.0f}% projects)",
      'source': f"{top_source} ({top_source_pct:.0f}% projects)"
    }
  else:
    results['debt'] = {'interest': 'N/A', 'repayment': 'N/A', 'type': 'N/A', 'source': 'N/A'}

  # ========== GRANTS ==========
  grants_df = df[df['category'] == 'Grants & non-repayable contributions']
  if len(grants_df) > 0:
    total_projects = grants_df['record_id'].nunique()

    source_counts = grants_df.groupby('source')['record_id'].nunique()
    top_source = source_counts.idxmax()
    top_source_pct = (source_counts.max() / total_projects * 100)

    mechanism_counts = grants_df.groupby('item_type')['record_id'].nunique()
    top_mechanism = mechanism_counts.idxmax() if len(mechanism_counts) > 0 else 'N/A'
    top_mechanism_pct = (mechanism_counts.max() / total_projects * 100) if len(mechanism_counts) > 0 else 0

    results['grants'] = {
      'type': f"{top_mechanism} ({top_mechanism_pct:.0f}% projects)",
      'source': f"{top_source} ({top_source_pct:.0f}% projects)"
    }
  else:
    results['grants'] = {'type': 'N/A', 'source': 'N/A'}

  # ========== COMMUNITY FINANCE ==========
  comm_df = df[df['category'] == 'Community finance']
  if len(comm_df) > 0:
    total_projects = comm_df['record_id'].nunique()

    source_counts = comm_df.groupby('source')['record_id'].nunique()
    top_source = source_counts.idxmax()
    top_source_pct = (source_counts.max() / total_projects * 100)

    mechanism_counts = comm_df.groupby('item_type')['record_id'].nunique()
    top_mechanism = mechanism_counts.idxmax() if len(mechanism_counts) > 0 else 'N/A'
    top_mechanism_pct = (mechanism_counts.max() / total_projects * 100) if len(mechanism_counts) > 0 else 0

    results['community_finance'] = {
      'type': f"{top_mechanism} ({top_mechanism_pct:.0f}% projects)",
      'source': f"{top_source} ({top_source_pct:.0f}% projects)"
    }
  else:
    results['community_finance'] = {'type': 'N/A', 'source': 'N/A'}

  # ========== CROWDFUNDING ==========
  crowd_df = df[df['category'] == 'Crowdfunding']
  if len(crowd_df) > 0:
    total_projects = crowd_df['record_id'].nunique()

    source_counts = crowd_df.groupby('source')['record_id'].nunique()
    top_source = source_counts.idxmax()
    top_source_pct = (source_counts.max() / total_projects * 100)

    mechanism_counts = crowd_df.groupby('item_type')['record_id'].nunique()
    top_mechanism = mechanism_counts.idxmax() if len(mechanism_counts) > 0 else 'N/A'
    top_mechanism_pct = (mechanism_counts.max() / total_projects * 100) if len(mechanism_counts) > 0 else 0

    results['crowdfunding'] = {
      'type': f"{top_mechanism} ({top_mechanism_pct:.0f}% projects)",
      'source': f"{top_source} ({top_source_pct:.0f}% projects)"
    }
  else:
    results['crowdfunding'] = {'type': 'N/A', 'source': 'N/A'}

  return results

def create_scale_pies_internal(df):
  """
  Create pie charts showing funding distribution by project scale.
  One pie chart per scale, showing breakdown by category.
  """
  from plotly.subplots import make_subplots

  # Define project scale order (smallest to largest)
  scale_order = [
    "Micro (< $100K)", 
    "Small ($100K-$1M)", 
    "Medium ($1M-$5M)", 
    "Large ($5M-$25M)", 
    "Very Large ($25M-$100M)",
    "Mega (> $100M)"
  ]

  # Filter to only scales present in data
  scales_in_data = [s for s in scale_order if s in df['project_scale'].values]

  if not scales_in_data:
    fig = go.Figure()
    fig.update_layout(title='No data available')
    return fig

  # Use record_id as the ID column
  id_col = 'record_id'

  # Create subplots - one pie per scale
  fig = make_subplots(
    rows=1, 
    cols=len(scales_in_data),
    specs=[[{'type': 'domain'}] * len(scales_in_data)],
    subplot_titles=list(scales_in_data)
  )

  # Add pie chart for each scale
  for i, scale in enumerate(scales_in_data):
    sub = df[df['project_scale'] == scale]
    grouped = sub.groupby('category', as_index=False)['amount'].sum()

    # Get colors for categories
    colors = [COLOUR_MAPPING.get(cat, '#808080') for cat in grouped['category']]

    fig.add_trace(
      go.Pie(
        labels=grouped['category'], 
        values=grouped['amount'], 
        name=scale,
        marker=dict(colors=colors),
        texttemplate='%{percent:.1%}',
        textposition='inside',
        textfont=dict(family='Arial, sans-serif', size=10, color='white'),
        sort=False,
        hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>',
        showlegend=(i == 0)  # Only show legend for first pie
      ),
      row=1, 
      col=i+1
    )

  # Update annotations with project counts
  for i, scale in enumerate(scales_in_data):
    n = df.loc[df['project_scale'] == scale, id_col].nunique()
    fig.layout.annotations[i]['text'] = f"{scale}<br>({n} projects)"
    fig.layout.annotations[i]['font'] = dict(family='Arial, sans-serif', size=14, color='black')
    fig.layout.annotations[i]['font'] = dict(family='Arial, sans-serif', size=14, color='black')
    fig.layout.annotations[i]['y'] = 0.9  # Lower the annotations

  # Update layout
  fig.update_layout(
    title={
      'text': 'Funding distribution by project scale',
      'font': {'family': 'Arial, sans-serif', 'size': 16, 'color': 'black'},
      'x': 0.01,
      'xanchor': 'left',
      'y': 0.99,
      'yanchor': 'top'
    },
    showlegend=True,
    legend=dict(orientation="h", y=0.01, x=0.5, xanchor='center'),
    plot_bgcolor='rgba(0, 0, 0, 0)',
    paper_bgcolor='rgba(0, 0, 0, 0)',
    font=dict(family='Arial, sans-serif', size=12, color='black'),
    margin=dict(l=0, r=0, t=35, b=0)
  )

  return fig