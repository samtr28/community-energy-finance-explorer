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

# ==================== OWNER TYPE CATEGORIES ====================
# Groups the 24 owner types into 6 colour categories.
# Used by get_owner_type_colors_categorical() — see below.

OWNER_TYPE_CATEGORIES = {
  # ── Community & Cooperative (teal family) ──
  'Benefit company (BC)':                                            'Community',
  'Community contribution company (BC)':                             'Community',
  'Community corporation':                                           'Community',
  'Cooperative association':                                         'Community',
  'Direct individual ownership from community members':              'Community',

  # ── Indigenous (amber/brown family) ──
  'Tribal Council/Regional First Nations, Métis or Inuit Government': 'Indigenous',
  'Indigenous coalition':                                             'Indigenous',
  'Indigenous energy corporation/utility':                            'Indigenous',
  'Community-held through Band Council or Indigenous community trust':'Indigenous',
  'Indigenous development corporation':                               'Indigenous',

  # ── Private / Investor (red family) ──
  'Bank':                                                            'Private',
  'Individual investor (outside community)':                         'Private',
  'For profit business entity':                                      'Private',
  'Insurer':                                                         'Private',
  'Loan corporation or trust corporation':                           'Private',

  # ── Public / Government (dark blue family) ──
  'Municipal energy corporation/utility (e.g., ENMAX, Nelson Hydro)': 'Public',
  'Municipality':                                                     'Public',
  'Sector-specific public organization (e.g., school board, irrigation district, public health)': 'Public',
  'Crown corporation (e.g., BC Hydro)':                               'Public',

  # ── Non-for-profit / Civil Society (purple family) ──
  'Non-for-profit organization/society':                             'Non-profit',
  'Registered charity':                                              'Non-profit',
  'Religious society':                                               'Non-profit',

  # ── Other / Unknown (grey) ──
  "Don't know":              'Other',
  'Other (Please specify)':  'Other',
}

# Base + (optional) secondary colour per category.
# When secondary is set, shades interpolate from base → secondary;
# otherwise shades scale around the base hue.
CATEGORY_COLOUR_SCHEME = {
  'Community':  {'base': dunsparce_colors[1], 'secondary': dunsparce_colors[5]},   # teal → dark teal
  'Indigenous': {'base': dunsparce_colors[4], 'secondary': dunsparce_colors[11]},  # amber → dark brown
  'Private':    {'base': dunsparce_colors[8], 'secondary': None},                  # red
  'Public':     {'base': dunsparce_colors[0], 'secondary': None},                  # dark blue
  'Non-profit': {'base': dunsparce_colors[9], 'secondary': None},                  # purple
  'Other':      {'base': dunsparce_colors[19],'secondary': None},                  # grey
}


def _hex_to_rgb(h):
  h = h.lstrip('#')
  return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _rgb_to_hex(r, g, b):
  return f'#{max(0,min(255,int(r))):02x}{max(0,min(255,int(g))):02x}{max(0,min(255,int(b))):02x}'

def _generate_category_shades(base_hex, secondary_hex=None, n=1):
  """Return n hex shades for a category.

  If secondary_hex is given, shades interpolate from base → secondary.
  Otherwise shades scale around the base (0.75x to 1.35x brightness).
  """
  if n <= 0:
    return []
  if n == 1:
    return [base_hex]

  r1, g1, b1 = _hex_to_rgb(base_hex)
  if secondary_hex:
    r2, g2, b2 = _hex_to_rgb(secondary_hex)
    return [
      _rgb_to_hex(
        r1 + (r2 - r1) * i / (n - 1),
        g1 + (g2 - g1) * i / (n - 1),
        b1 + (b2 - b1) * i / (n - 1),
      )
      for i in range(n)
    ]
  # No secondary: shade-shift around the base
  return [
    _rgb_to_hex(
      r1 * (0.75 + 0.6 * i / (n - 1)),
      g1 * (0.75 + 0.6 * i / (n - 1)),
      b1 * (0.75 + 0.6 * i / (n - 1)),
    )
    for i in range(n)
  ]


def get_owner_type_colors_categorical(owner_types_list):
  """
  Assign hex colours to owner types grouped by category.
  Types in the same category get shades of the same base colour.

  Returns: dict {owner_type: hex_color}
  """
  by_category = {}
  for ot in owner_types_list:
    cat = OWNER_TYPE_CATEGORIES.get(ot, 'Other')
    by_category.setdefault(cat, []).append(ot)

  result = {}
  for cat, types in by_category.items():
    scheme = CATEGORY_COLOUR_SCHEME.get(cat, CATEGORY_COLOUR_SCHEME['Other'])
    shades = _generate_category_shades(scheme['base'], scheme.get('secondary'), len(types))
    for t, shade in zip(sorted(types), shades):
      result[t] = shade
  return result

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