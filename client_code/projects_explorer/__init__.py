from ._anvil_designer import projects_explorerTemplate
from anvil import *
import m3.components as m3
import plotly.graph_objects as go
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.js
from .AutoScroll import AutoScroll
from .Project_Card import Project_Card  # Import the card component


class projects_explorer(projects_explorerTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)
    self._hi_card = None
    self._selected_idx = None
    self._current_filters = {}
    self._all_card_data = []  # Store all card data
    self._cards_displayed = 0  # Track how many cards are displayed
    self._auto_scroll = None

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.projects_nav.role = 'selected'
  
    # Configure map appearance
    self.project_map.layout.map = dict(center=dict(lat=57, lon=-97), zoom=2, style="carto-voyager")
    self.project_map.layout.template = "mykonos_light"
    self.project_map.layout.margin = dict(t=5, b=5, l=5, r=5)
  
    # Load initial data
    self.apply_filters()

    
  # ============ FILTER FUNCTIONS ============
  def schedule_filter_update(self):
    """Schedule a filter update with debouncing"""
    self.filter_timer.interval = 1


  def apply_filters(self):
    """Apply filters and load ALL card data"""
    # Read current filter selections
    provinces = self.provinces_dd.selected
    proj_types = self.proj_types_dd.selected
    stages = self.stages_dd.selected
    indigenous_ownership = self.indig_owners_dd.selected
    project_scale = self.project_scale_dd.selected

    # Build kwargs
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

    # Store filters
    self._current_filters = kwargs

    # Load all cards WITHOUT traces
    print("Fetching all cards (no traces)...")
    all_data = anvil.server.call('get_all_cards_minimal', **kwargs)
    print(f"Received {all_data['total_count']} cards")

    # Update map (all points)
    self.project_map.data = [all_data['map_data']]

    # Store card data
    self._all_card_data = all_data['project_cards']
    self._cards_displayed = 0

    # Clear existing cards
    self.project_cards.clear()

    print(f"Stored {len(self._all_card_data)} cards")

    # Load first batch immediately
    print("Loading first batch...")
    self.load_next_cards(batch_size=20)

    # Start the scroll check timer
    if hasattr(self, 'scroll_check_timer'):
      self.scroll_check_timer.interval = 0.5  # Start checking

  def check_scroll_position(self, **event_args):
    """Check if we need to load more cards based on scroll position"""
    # If all cards displayed, stop checking
    if self._cards_displayed >= len(self._all_card_data):
      self.scroll_check_timer.interval = 0  # Stop timer
      print("All cards loaded, stopping scroll check")
      return
  
      # Check if the last displayed card is visible
      # Simple heuristic: load more if we're past the first batch
    if self._cards_displayed < len(self._all_card_data):
      # Load next batch
      print("Timer triggered, loading next batch...")
      self.load_next_cards(batch_size=20)

  def filter_timer_tick(self, **event_args):
    """This method is called when the timer fires"""
    self.filter_timer.interval = 0
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

  # ============ AUTO-SCROLL LOADING ============
  def load_next_cards(self, batch_size=20):
    """
    Called by AutoScroll when user scrolls near bottom.
    Adds next batch of cards to LinearPanel.
    Returns True if more available, False if done.
    """
    total_cards = len(self._all_card_data)

    # Check if all done
    if self._cards_displayed >= total_cards:
      print("✅ All cards displayed!")
      return False

    start_idx = self._cards_displayed
    end_idx = min(start_idx + batch_size, total_cards)

    print(f"📊 Loading cards {start_idx} to {end_idx}...")

    # First, build traces for this batch
    try:
      traces_list = anvil.server.call(
        'build_traces_batch',
        start_idx,
        batch_size,
        **self._current_filters
      )

      # Create a map for quick lookup
      traces_map = {t['record_id']: t for t in traces_list}

      # Add cards to LinearPanel one by one
      for i in range(start_idx, end_idx):
        card_data = self._all_card_data[i].copy()
        record_id = card_data['record_id']

        # Add traces if available
        if record_id in traces_map:
          card_data['ownership_traces'] = traces_map[record_id]['ownership_traces']
          card_data['capital_mix_traces'] = traces_map[record_id]['capital_mix_traces']

        # Create and add the card component
        card_component = Project_Card(item=card_data)
        self.project_cards.add_component(card_component)

      # Update progress
      self._cards_displayed = end_idx

      print(f"✅ Displayed cards up to {end_idx}/{total_cards}")

      # Return True if more available
      return end_idx < total_cards

    except Exception as e:
      print(f"❌ Error loading cards: {e}")
      import traceback
      traceback.print_exc()
      return False

  # ============ MAP CLICK - ON DEMAND ============
  def _select_index(self, idx: int):
    """Highlight point idx on the map and the matching card."""
    print(f"\n🎯 Map click on card {idx}")

    # Map: select just this point
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = [idx]
      self.project_map.figure = fig

    # If the card isn't displayed yet, we need to load up to it
    if idx >= self._cards_displayed:
      print(f"  Card {idx} not displayed yet, loading up to it...")
      self._load_up_to_index(idx)

    # Card: scroll + highlight
    card_components = self.project_cards.get_components()
    if 0 <= idx < len(card_components):
      card = card_components[idx]
      card.scroll_into_view()

      # Clear previous highlight
      if self._hi_card:
        self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()

      card.role = ((card.role or "") + " card-highlight").strip()
      self._hi_card = card

    # Track current selection
    self._selected_idx = idx

  def _load_up_to_index(self, target_idx):
    """Load all cards up to and including target_idx"""
    if target_idx >= len(self._all_card_data):
      return

    # Calculate how many batches we need
    cards_needed = target_idx + 1 - self._cards_displayed

    if cards_needed <= 0:
      return  # Already loaded

    print(f"  Loading {cards_needed} cards to reach index {target_idx}...")

    # Load in one go
    start_idx = self._cards_displayed
    end_idx = target_idx + 1

    try:
      # Build traces for all needed cards
      traces_list = anvil.server.call(
        'build_traces_batch',
        start_idx,
        cards_needed,
        **self._current_filters
      )

      traces_map = {t['record_id']: t for t in traces_list}

      # Add all cards up to target
      for i in range(start_idx, end_idx):
        card_data = self._all_card_data[i].copy()
        record_id = card_data['record_id']

        if record_id in traces_map:
          card_data['ownership_traces'] = traces_map[record_id]['ownership_traces']
          card_data['capital_mix_traces'] = traces_map[record_id]['capital_mix_traces']

        card_component = Project_Card(item=card_data)
        self.project_cards.add_component(card_component)

      self._cards_displayed = end_idx
      print(f"  ✅ Loaded cards up to {end_idx}")

    except Exception as e:
      print(f"  ❌ Error loading cards: {e}")

  def _unselect_all(self):
    """Clear selection from both map and cards."""
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = []
      self.project_map.figure = fig

    if self._hi_card:
      self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      self._hi_card = None

    self._selected_idx = None

  def project_map_click(self, points, **event_args):
    """Handle map click events"""
    if not points:
      self._unselect_all()
      return

    idx = points[0]["point_number"]

    if self._selected_idx == idx:
      self._unselect_all()
    else:
      self._select_index(idx)

  # ============ OTHER EVENTS ============
  def load_more_button_click(self, **event_args):
    """This method is called when the component is clicked."""
    pass

  @handle("scroll_check_timer", "tick")
  def scroll_check_timer_tick(self, **event_args):
    """This method is called Every [interval] seconds. Does not trigger if [interval] is 0."""
    # If all cards displayed, stop timer
    if self._cards_displayed >= len(self._all_card_data):
      self.scroll_check_timer.interval = 0  # Stop timer
      print("✅ All cards loaded, stopping timer")
      return

    # Load next batch
    print("Timer tick - loading next batch...")
    self.load_next_cards(batch_size=20)
    pass
