# config.py — Client module
# =========================
# Colours, palettes, and font constants shared across the whole app.
# This is a CLIENT module — importable from both client forms and server modules.
# Do NOT import server-only libraries (plotly, pandas, etc.) here.

from anvil import app


# ==================== DISPLAY FONT CONSTANTS ====================
# Used by apply_display_template() in Export_Utils.py (server)
# and available to client forms for any custom UI styling.

FONT_FAMILY  = 'Arial, sans-serif'   # body — tick labels, legend, bar text
TITLE_FONT_FAMILY = 'Georgia, serif' # title — serif contrasts clearly with sans-serif body
FONT_SIZE   = 14   # base size — tick labels, legend, hover, bar text
FONT_COLOR  = 'black'
TITLE_SIZE  = 20    # noticeably larger than body text
TITLE_PAD_B = 14    # pixels of space between title and plot area
MARGIN_TOP  = 52    # top margin — must be large enough to fit the title


# ==================== COLOUR PALETTE ====================

# Dunsparce palette — full ordered list
dunsparce_colors = [
  '#005694',  # 0  dark blue
  '#0FAFB9',  # 1  teal
  '#d7da7c',  # 2  yellow-green
  '#76b37f',  # 3  green
  '#f5aa1c',  # 4  amber
  '#00504a',  # 5  dark teal
  '#DE7002',  # 6  orange
  '#83d5ca',  # 7  light teal
  '#c63527',  # 8  red
  '#7b38c7',  # 9  purple
  '#CAEFF1',  # 10 very light teal
  '#7e570f',  # 11 dark brown
  '#002754',  # 12 navy
  '#F9D88B',  # 13 light yellow
  '#2d847b',  # 14 slate teal
  '#c2ddff',  # 15 light blue
  '#392000',  # 16 very dark brown
  '#e99286',  # 17 salmon
  '#f8f8f8',  # 18 off-white
  '#8e9099',  # 19 grey
]

# Gradient palette (dark teal → dark brown, for sequential data)
gradient_palette = [
  '#003c30', '#01665e', '#35978f', '#80cdc1', '#c7eae5',
  '#f5f5f5', '#f6e8c3', '#dfc27d', '#bf812d', '#8c510a', '#543005'
]


# ==================== CATEGORY COLOUR MAPPING ====================
# Maps financing category names (and their variants) to brand colours.

COLOUR_MAPPING = {
  # Grants
  'Grants':                                     '#005694',
  'Grants & non-repayable contributions':       '#005694',
  # Equity
  'Equity':                                     '#d7da7c',
  'External equity investments':                '#d7da7c',
  # Debt
  'Debt':                                       '#c63527',
  'Debt financing':                             '#c63527',
  # Crowdfunding
  'Crowdfund':                                  '#7b38c7',
  'Crowdfunding campaigns':                     '#7b38c7',
  'Crowdfunding':                               '#7b38c7',
  # Internal capital
  'Internal capital':                           '#76b37f',
  'Internal/owner-contributed capital':         '#76b37f',
  # Community finance
  'Community finance':                          '#0FAFB9',
  'Community finance models':                   '#0FAFB9',
  'Community financing':                        '#0FAFB9',
  # Other financing types
  'Tax credits':                                '#f5aa1c',
  'Tax credits/accelerated depreciation':       '#f5aa1c',
  'Loan guarantees':                            '#DE7002',
  'Loan guarantees/credit enhancements':        '#DE7002',
  'Leasing':                                    '#7e570f',
  'Leasing/third-party ownership models':       '#7e570f',
  'Public Private Partnership (P3)':            '#2d847b',
  'Public Private Partnership':                 '#2d847b',
  'Feed-in tariffs/power purchase agreements':  '#00504a',
  'Other':                                      '#8e9099',
}

# Default category display order
CATEGORY_ORDER = [
  'Crowdfunding', 'Community finance', 'Grants', 'Debt', 'Equity', 'Internal capital'
]


# ==================== PROJECT TYPE COLOURS ====================

PROJECT_TYPE_COLORS = {
  'Solar':                        '#f5aa1c',
  'Wind':                         '#c2ddff',
  'Hydro':                        '#005694',
  'Geothermal':                   '#c63527',
  'Biomass':                      '#76b37f',
  'Biofuel/Biogas':               '#d7da7c',
  'Hydrogen':                     '#83d5ca',
  'Energy storage':               '#7b38c7',
  'Building efficiency upgrades': '#2d847b',
  'Waste to energy':              '#7e570f',
  'Tidal/wave':                   '#002754',
  'Microgrid':                    '#0FAFB9',
  'Electro-mobility':             '#00504a',
}

def get_project_type_color(project_type):
  """Return the brand colour for a project type, falling back to grey."""
  return PROJECT_TYPE_COLORS.get(project_type, '#8e9099')


# ==================== OWNER TYPE COLOURS ====================

def get_owner_type_colors(owner_types_list, palette='dunsparce'):
  """
  Assign colours from a palette to a list of owner types.

  Args:
    owner_types_list: list of unique owner type strings
    palette:          'dunsparce', 'gradient', or a custom list of hex strings

  Returns:
    dict mapping each owner type to a hex colour string
  """
  colors = (
    dunsparce_colors if palette == 'dunsparce' else
    gradient_palette if palette == 'gradient'  else
    palette          if isinstance(palette, list) else
    dunsparce_colors
  )
  return {t: colors[i % len(colors)] for i, t in enumerate(sorted(owner_types_list))}