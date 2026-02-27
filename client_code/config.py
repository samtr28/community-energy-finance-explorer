import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from anvil import app

##### COLOUR SCHEME

# Dunsparce palette - exact order from screenshot
# Left column:  #005694, #0FAFB9, #d7da7c, #76b37f, #f5aa1c, #00504a, #DE7002, #83d5ca, #c63527, #7b38c7, #CAEFF1, #002754
# Right column: #F9D88B, #DE7002, #2d847b, #c2ddff, #7e570f, #392000, #f8f8f8, #8e9099

dunsparce_colors = [
  '#005694',  # dark blue
  '#0FAFB9',  # teal
  '#d7da7c',  # yellow-green
  '#76b37f',  # green
  '#f5aa1c',  # amber
  '#00504a',  # dark teal
  '#DE7002',  # orange
  '#83d5ca',  # light teal
  '#c63527',  # red
  '#7b38c7',  # purple
  '#CAEFF1',  # very light teal
  '#7e570f',  # dark brown
  '#002754',  # navy
  '#F9D88B',  # light yellow
  '#2d847b',  # slate teal
  '#c2ddff',  # light blue
  '#392000',  # very dark brown
  '#e99286',  # salmon/orange (right col)
  '#f8f8f8',  # off-white
  '#8e9099',  # grey
]

COLOUR_MAPPING = {
  'Grants':                                    '#005694',  # dark blue
  'Grants & non-repayable contributions':      '#005694',
  'Equity':                                    '#d7da7c',  # yellow-green
  'External equity investments':               '#d7da7c',
  'Debt':                                      '#c63527',  # red
  'Debt financing':                            '#c63527',
  'Crowdfund':                                 '#7b38c7',  # purple
  'Crowdfunding campaigns':                    '#7b38c7',
  'Crowdfunding':                              '#7b38c7',
  'Internal capital':                          '#76b37f',  # green
  'Internal/owner-contributed capital':        '#76b37f',
  'Community finance':                         '#0FAFB9',  # teal
  'Community finance models':                  '#0FAFB9',
  'Community financing':                       '#0FAFB9',
  'Tax credits':                               '#f5aa1c',  # amber
  'Tax credits/accelerated depreciation':      '#f5aa1c',
  'Loan guarantees':                           '#DE7002',  # orange
  'Loan guarantees/credit enhancements':       '#DE7002',
  'Leasing':                                   '#7e570f',  # dark brown
  'Leasing/third-party ownership models':      '#7e570f',
  'Public Private Partnership (P3)':           '#2d847b',  # slate teal
  'Public Private Partnership':               '#2d847b',
  'Feed-in tariffs/power purchase agreements': '#00504a',  # dark teal
  'Other':                                     '#8e9099',  # grey
}

# Gradient palette (from dark teal to dark brown)
gradient_palette = [
  '#003c30',
  '#01665e',
  '#35978f',
  '#80cdc1',
  '#c7eae5',
  '#f5f5f5',
  '#f6e8c3',
  '#dfc27d',
  '#bf812d',
  '#8c510a',
  '#543005'
]
# Category display order (bottom to top for stacked bar, left to right for box plot)
CATEGORY_ORDER = [
  'Crowdfunding',
  'Community finance',
  'Grants',
  'Debt',
  'Equity',
  'Internal capital'
]

##### OWNERSHIP COLOR MAPPING
# Function to automatically assign colors to owner types
def get_owner_type_colors(owner_types_list, palette='dunsparce'):
  """
  Automatically assign colors to a list of owner types.
  
  Args:
    owner_types_list: List of unique owner types
    palette: 'dunsparce', 'gradient', or list of hex colors
  
  Returns:
    Dictionary mapping owner_type to color
  """
  # Choose palette
  if palette == 'dunsparce':
    colors = dunsparce_colors
  elif palette == 'gradient':
    colors = gradient_palette
  elif isinstance(palette, list):
    colors = palette
  else:
    colors = dunsparce_colors  # Default

  # Sort for consistency
  sorted_types = sorted(owner_types_list)

  # Assign colors
  return {
    owner_type: colors[i % len(colors)] 
    for i, owner_type in enumerate(sorted_types)
  }