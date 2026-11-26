import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

"""
One definition of every filter. Add, remove, reorder or rename a filter here only.
The order of FILTERS is the order of the dropdowns on the page.

key         kwarg name sent to the server
column      dataframe column the server filters on
kind        'in'          -> the column holds one value
            'any_in_list' -> the column holds a list; match if any selected value is in it
label       dropdown placeholder
chip        prefix shown on the chips
export      label used on exported charts
items       fixed dropdown items (leave out when items_from is used)
items_from  'data'          -> items are the values found in the data column
            'owner_options' -> items come from the owners data (see Filtering.py)
depends_on  this dropdown's items depend on another filter's selection
expand      maps a dropdown choice to the real data values it stands for
"""

MIN_RESPONSES_SHOWN        = 3    # survey responses; below this, anonymous ones are hidden
SMALL_SAMPLE_WARNING_BELOW = 5    # projects; below this, add the small-sample note
NARROW_SCREEN_PX           = 998  # filters start collapsed below this width
DROPDOWN_PADDING_PX   = 72    # room for the chevron and padding around the label
DROPDOWN_MIN_WIDTH_PX = 110
FILTER_DEBOUNCE_SECONDS = 0.4

# How the data marks anonymous projects (same column get_data() already uses)
ANON_COLUMN = 'anonymous_status'
ANON_VALUE  = 'anon'

MESSAGES = {
  'hidden':   "Either there is no data for these filters, or the data cannot be shown to protect anonymity.",
  'count':    "Showing {n} of {total} projects.",
  'partial':  "Showing {n} {noun}. Some projects are hidden to protect anonymity.",
  'excluded': "{label} filter excludes {items}.",
  'small':    "Based on a small number of projects, so interpret with caution.",
  'excluded_default': "The {label} filter excludes {items} by default, because very large projects can skew the results. Clear the filters to include them.",
}
# Left side = text shown in the dropdown. Right side = the real values in the data.
INDIG_MAP = {
  'Majority (51-100%)': [
    'Wholly Indigenous owned (100%)',
    'Majority Indigenous owned (51-99%)',
  ],
  'Minority (1-50%)': [
    'Half Indigenous owned (50%)',
    'Minority Indigenous owned (1-49%)',
  ],
  'None (0%)': ['No Indigenous ownership'],
}

FILTERS = [
  {'key': 'proj_types', 'column': 'project_type', 'kind': 'any_in_list',
   'label': 'Technology', 'chip': 'Technology', 'export': 'Project Types',
   'items_from': 'data'},

  {'key': 'provinces', 'column': 'province', 'kind': 'in',
   'label': 'Province/Territory', 'chip': 'Province', 'export': 'Provinces',
   'items': ['Alberta', 'British Columbia', 'Manitoba', 'New Brunswick',
             'Newfoundland and Labrador', 'Northwest Territories', 'Nova Scotia', 'Nunavut',
             'Ontario', 'Prince Edward Island', 'Quebec', 'Saskatchewan', 'Yukon']},

  {'key': 'stages', 'column': 'stage', 'kind': 'in',
   'label': 'Project Stage', 'chip': 'Stage', 'export': 'Stages',
   'items': ['Construction', 'Operation']},

  {'key': 'owner_categories', 'column': 'owner_categories', 'kind': 'any_in_list',
   'label': 'Owner Type(s)', 'chip': 'Owner Type', 'export': 'Owner Type',
   'items_from': 'owner_options'},

  {'key': 'owner_types', 'column': 'owner_types', 'kind': 'any_in_list',
   'label': 'Owner Subtype(s)', 'chip': 'Owner Subtype', 'export': 'Owner Subtype',
   'items_from': 'owner_options', 'depends_on': 'owner_categories'},

  {'key': 'indigenous_ownership', 'column': 'indigenous_ownership', 'kind': 'in',
   'label': 'Indigenous Ownership Share', 'chip': 'Indigenous Share', 'export': 'Indigenous Share',
   'items': list(INDIG_MAP), 'expand': INDIG_MAP},

  {'key': 'project_scale', 'column': 'project_scale', 'kind': 'in',
   'label': 'Project Scale', 'chip': 'Scale', 'export': 'Project Scale',
   'note_excluded': True,
   'items': ['Micro (< $100K)', 'Small ($100K-$1M)', 'Medium ($1M-$5M)',
             'Large ($5M-$25M)', 'Very Large ($25M-$100M)', 'Mega (> $100M)']},
]

# Display order for owner categories in the dropdown (unknown ones go last).
OWNER_CATEGORY_ORDER = ['Community-based', 'Indigenous', 'Private sector',
                        'Public sector', 'Non-profit', 'Other / Unknown']