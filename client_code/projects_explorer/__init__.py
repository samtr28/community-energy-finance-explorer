from ._anvil_designer import projects_explorerTemplate
from anvil import *
import m3.components as m3
import plotly.graph_objects as go
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.js


class projects_explorer(projects_explorerTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)
    self._hi_card = None
    self._selected_idx = None

    # Pagination state
    self._current_page = 1
    self._page_size = 10
    self._total_count = 0
    self._loaded_pages = set()  # Track which pages we've loaded
    self._start_idx = 0  # Start index of currently loaded cards

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.projects_nav.role = 'selected'

    # Configure map appearance
    self.project_map.layout.map = dict(center=dict(lat=57, lon=-97), zoom=2, style="carto-voyager")
    self.project_map.layout.template = "mykonos_light"
    self.project_map.layout.margin = dict(t=5, b=5, l=5, r=5)

    # Hide Load More button initially
    self.load_more_button.visible = False

    # Load initial data when form is shown
    self.apply_filters()

  # ============ FILTER FUNCTIONS ============
  def schedule_filter_update(self):
    """Schedule a filter update with debouncing - waits 300ms after last change"""
    self.filter_timer.interval = 0.3

  def apply_filters(self, reset_page=True, page=None):
    """Apply filters and update map + cards with ONE server call"""
    if reset_page:
      self._current_page = 1
      self._loaded_pages = set()
      self._start_idx = 0

    if page is not None:
      self._current_page = page

    # Read current filter selections
    provinces = self.provinces_dd.selected
    proj_types = self.proj_types_dd.selected
    stages = self.stages_dd.selected
    indigenous_ownership = self.indig_owners_dd.selected
    project_scale = self.project_scale_dd.selected

    # Build kwargs with only set filters
    kwargs = {}
    if provinces:
      kwargs["provinces"] = provinces
    if proj_types:
      kwargs["proj_types"] = proj_types
    if stages:
      kwargs["stages"] = stages
    if indigenous_ownership:
      kwargs["indigenous_ownership"] = indigenous_ownership
    if project_scale:
      kwargs["project_scale"] = project_scale

    # Add pagination parameters
    kwargs["page"] = self._current_page
    kwargs["page_size"] = self._page_size

    # SINGLE SERVER CALL - gets both map and cards at once
    print(f"Fetching page {self._current_page}...")
    all_data = anvil.server.call('get_all_map_and_cards', **kwargs)
    print("Data received, updating UI...")

    # Update map (only on first page or filter change)
    if reset_page or self._current_page == 1:
      self.project_map.data = [all_data['map_data']]

    # Update project cards
    if reset_page or self._current_page == 1:
      # Replace cards (new filter or first page)
      self.project_cards.items = all_data['project_cards']
      self._start_idx = all_data['start_idx']
    else:
      # Append cards (Load More clicked)
      self.project_cards.items += all_data['project_cards']

    # Track loaded state
    self._loaded_pages.add(self._current_page)
    self._total_count = all_data['total_count']

    # Show/hide Load More button
    self.load_more_button.visible = all_data['has_more']

    # Update button text with count
    remaining = self._total_count - len(self.project_cards.items)
    self.load_more_button.text = f"Load More ({remaining} remaining)"

    print(f"Loaded {len(self.project_cards.items)} of {self._total_count} total cards")

  def filter_timer_tick(self, **event_args):
    """This method is called when the timer fires"""
    self.filter_timer.interval = 0  # Stop the timer
    self.apply_filters()

  # ============ DROPDOWN CHANGE EVENTS ============
  def provinces_dd_change(self, **event_args):
    self.schedule_filter_update()

  def proj_types_dd_change(self, **event_args):
    self.schedule_filter_update()

  def stages_dd_change(self, **event_args):
    self.schedule_filter_update()

  def indig_owners_dd_change(self, **event_args):
    self.schedule_filter_update()

  def project_scale_dd_change(self, **event_args):
    self.schedule_filter_update()

  # ============ MAP CLICK EVENTS ============
  def _select_index(self, idx: int):
    """Highlight point idx on the map and the matching card."""
    # Map: select just this point
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = [idx]
      self.project_map.figure = fig

    # Calculate which card index this is in our loaded cards
    # idx is the position in the FULL filtered dataset
    # We need to find it in our currently loaded cards
    card_idx = idx - self._start_idx

    # Card: scroll + highlight
    rows = self.project_cards.get_components()
    if 0 <= card_idx < len(rows):
      row = rows[card_idx]
      row.scroll_into_view()

      # Clear previous highlight
      if self._hi_card:
        self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()

      row.project_card.role = ((row.project_card.role or "") + " card-highlight").strip()
      self._hi_card = row.project_card

    # Track current selection
    self._selected_idx = idx

  def _unselect_all(self):
    """Clear selection from both map and cards."""
    # Map: clear selection
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = []
      self.project_map.figure = fig

    # Card: remove highlight
    if self._hi_card:
      self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      self._hi_card = None

    # Clear tracking
    self._selected_idx = None

  def _load_pages_up_to_index(self, target_idx):
    """Load all pages necessary to show the card at target_idx"""
    # Calculate which page the target is on
    target_page = (target_idx // self._page_size) + 1

    print(f"Target index {target_idx} is on page {target_page}")

    # Calculate how many cards we need total
    cards_needed = target_idx + 1  # +1 because idx is 0-based
    cards_loaded = len(self.project_cards.items)

    if cards_loaded >= cards_needed:
      # We already have the card loaded
      print("Card already loaded")
      return

    # Load pages sequentially until we have enough cards
    # Start from the page after our currently loaded data
    current_last_page = (cards_loaded // self._page_size) if cards_loaded > 0 else 0
    if current_last_page == 0:
      current_last_page = 1

    for page_num in range(current_last_page + 1, target_page + 1):
      print(f"Loading page {page_num}...")
      self.apply_filters(reset_page=False, page=page_num)

  def project_map_click(self, points, **event_args):
    """Handle map click events - navigate to the page if needed"""
    if not points:
      # Clicked empty area - unselect
      self._unselect_all()
      return

    idx = points[0]["point_number"]

    print(f"Map clicked: point {idx}")

    # Toggle: if clicking same point, unselect
    if self._selected_idx == idx:
      self._unselect_all()
      return

    # Check if we need to load more pages to show this card
    cards_loaded = len(self.project_cards.items)

    if idx >= cards_loaded:
      # Need to load more pages
      print(f"Need to load more pages (have {cards_loaded} cards, need {idx + 1})")
      self._load_pages_up_to_index(idx)

    # Now select the card
    self._select_index(idx)

  # ============ OTHER EVENTS ============
  @handle("load_more_button", "click")
  def load_more_button_click(self, **event_args):
    """Load the next page of cards"""
    self._current_page += 1
    self.apply_filters(reset_page=False)