import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from anvil import app


##### COLOUR SCHEME
COLOUR_MAPPING = {
  'Grants': '#005493',
  'Grants & non-repayable contributions': '#005493',
  'Equity': '#d7da7c',
  'External equity investments':'#d7da7c',
  'Debt': '#c63527',
  'Debt financing': '#c63527',
  'Crowdfund': '#7b38c7',
  'Crowdfunding campaigns': '#7b38c7',
  'Crowdfunding':'#7b38c7',
  'Internal capital': '#76b37f',
  'Internal/owner-contributed capital': '#76b37f',
  'Community finance': '#0db0ba',
  'Community finance models': '#0db0ba',
  'Community financing':'#0db0ba',
  'Other': '#f8f8f8',
  'Tax credits': '#f5aa1c',
  'Tax credits/accelerated depreciation': '#f5aa1c',
  'Loan guarantees': '#fd9486',
  'Loan guarantees/credit enhancements': '#fd9486',
  'Leasing': '#825512',
  'Leasing/third-party ownership models': '#825512',
  'Public Private Partnership (P3)': '#2d847b',
  'Public Private Partnership': '#2d847b',
  'Feed-in tariffs/power purchase agreements':'#00504a'
  
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

# Dunsparce colors from screenshot
dunsparce_colors = [
  '#005493',
  '#0db0ba',
  '#d7da7c',
  '#76b37f',
  '#f5aa1c',
  '#00504a',
  '#825512',
  '#83d5ca',
  '#c63527',
  '#7b38c7',
  '#8e9099',
  '#002754',
  '#2d847b',
  '#c6e6e1',
  '#ffeed5',
  '#ffeed5',
  '#F8F8F8',
  '#d7da7c',
  '#392000'
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