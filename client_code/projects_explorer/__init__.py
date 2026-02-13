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
from .Project_Card import Project_Card


class projects_explorer(projects_explorerTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)
    self._hi_card = None
    self._selected_idx = None
    self._current_filters = {}
    self._total_cards = 0
    self._cards_loaded = 0
    self._auto_scroll = None
    self._background_loading = False

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
    self.filter_timer.interval = 1

  def apply_filters(self):
    """Apply filters - load map and start card loading"""
    print("\n========== APPLY FILTERS CALLED ==========")

    # Read filter selections
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
    print(f"Filters: {kwargs}")

    # Stop any background loading
    self.background_load_timer.interval = 0
    self._background_loading = False

    # Load map data only (fast!)
    print("Loading map...")
    map_data = anvil.server.call('get_map_data_only', **kwargs)

    # Update map
    self.project_map.data = [map_data['map_data']]
    self._total_cards = map_data['total_count']

    print(f"Map loaded with {self._total_cards} points")

    # Clear existing cards
    print("Clearing LinearPanel...")
    self.project_cards.clear()
    self._cards_loaded = 0

    print(f"LinearPanel cleared. Component count: {len(self.project_cards.get_components())}")

    # Check if project_cards exists and is accessible
    print(f"project_cards type: {type(self.project_cards)}")
    print(f"project_cards visible: {self.project_cards.visible}")

    # Load FIRST batch immediately for instant display
    print("\n========== LOADING FIRST BATCH ==========")
    success = self.load_next_page(n_rows=20)
    print(f"First batch load result: {success}")
    print(f"Cards in LinearPanel after first load: {len(self.project_cards.get_components())}")
    print(f"Cards loaded counter: {self._cards_loaded}")

    if self._cards_loaded == 0:
      print("⚠️ WARNING: No cards loaded! Check server response.")
    else:
      print(f"✅ Successfully loaded {self._cards_loaded} cards")

    # Start background loading for the rest
    if self._cards_loaded < self._total_cards and self._cards_loaded > 0:
      print("Starting background loading for remaining cards...")
      self._background_loading = True
      self.background_load_timer.interval = 0.5  # Load every 500ms
    else:
      print("Not starting background loading")

    # Set up AutoScroll (for user scrolling past loaded content)
    if self._auto_scroll is None:
      print("Setting up AutoScroll...")
      self._auto_scroll = AutoScroll(
        self.load_next_page,
        scrollbar_load_threshold=400,
        start_loading=False,
        debugging=False
      )

    print("========== APPLY FILTERS COMPLETE ==========\n")

  def filter_timer_tick(self, **event_args):
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

  # ============ BACKGROUND LOADING ============
  def background_load_timer_tick(self, **event_args):
    """Background loading - quietly loads cards without user noticing"""
    if not self._background_loading:
      return

    # Check if done
    if self._cards_loaded >= self._total_cards:
      print("✅ All cards loaded in background!")
      self.background_load_timer.interval = 0  # Stop timer
      self._background_loading = False
      return

    # Load next batch silently
    result = self.load_next_page(n_rows=20, silent=True)

    if not result:
      # No more data
      self.background_load_timer.interval = 0
      self._background_loading = False

  # ============ CARD LOADING ============
  def load_next_page(self, n_rows=20, silent=False):
    """
    Load next batch of cards from server.
    silent=True suppresses console output for background loading.
    """
    if not silent:
      print(f"\n📊 === LOAD_NEXT_PAGE CALLED ===")
      print(f"  Cards loaded so far: {self._cards_loaded}/{self._total_cards}")
      print(f"  Requesting: {n_rows} cards")

    # Check if done
    if self._cards_loaded >= self._total_cards:
      if not silent:
        print("✅ All cards already loaded!")
      return False  # No more data

    try:
      # Get next batch from server (WITH traces already built!)
      if not silent:
        print(f"  Calling server: get_card_batch(from_row={self._cards_loaded}, n_rows={n_rows})")

      cards = anvil.server.call(
        'get_card_batch',
        from_row=self._cards_loaded,
        n_rows=n_rows,
        **self._current_filters
      )

      if not silent:
        print(f"  ✅ Server returned {len(cards)} cards")
        if len(cards) > 0:
          print(f"  First card record_id: {cards[0].get('record_id')}")
          print(f"  First card has ownership_traces: {len(cards[0].get('ownership_traces', []))} traces")
          print(f"  First card has capital_mix_traces: {len(cards[0].get('capital_mix_traces', []))} traces")

      # Add each card to LinearPanel
      cards_added = 0
      for i, card_data in enumerate(cards):
        try:
          if not silent and i == 0:
            print(f"  Creating Project_Card component for first card...")

          card_component = Project_Card(item=card_data)

          if not silent and i == 0:
            print(f"  Project_Card created successfully")
            print(f"  Adding to LinearPanel...")

          self.project_cards.add_component(card_component)
          cards_added += 1

          if not silent and i == 0:
            print(f"  Added to LinearPanel successfully")
        except Exception as card_error:
          print(f"  ❌ Error creating/adding card {i}: {card_error}")
          import traceback
          traceback.print_exc()

      if not silent:
        print(f"  Successfully added {cards_added} cards to LinearPanel")
        print(f"  LinearPanel now has {len(self.project_cards.get_components())} components")

      # Update progress
      self._cards_loaded += len(cards)

      if not silent:
        print(f"✅ Total cards loaded: {self._cards_loaded}/{self._total_cards}")

      # Return True if more cards available
      return self._cards_loaded < self._total_cards

    except Exception as e:
      print(f"❌ EXCEPTION in load_next_page: {e}")
      import traceback
      traceback.print_exc()
      return False

  # ============ MAP CLICK ============
  def _select_index(self, idx: int):
    """Highlight point idx on the map and the matching card."""
    print(f"\n🎯 Map click on card {idx}")

    # Map: select point
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = [idx]
      self.project_map.figure = fig

    # If card not loaded yet, load up to it IMMEDIATELY
    if idx >= self._cards_loaded:
      print(f"  Card {idx} not loaded yet, loading immediately...")

      # Pause background loading temporarily
      was_background_loading = self._background_loading
      if was_background_loading:
        self.background_load_timer.interval = 0
        self._background_loading = False

      # Load up to the target
      self._load_up_to_index(idx)

      # Resume background loading if it was active
      if was_background_loading:
        self._background_loading = True
        self.background_load_timer.interval = 0.5

    # Scroll and highlight
    card_components = self.project_cards.get_components()
    if 0 <= idx < len(card_components):
      card = card_components[idx]
      card.scroll_into_view()

      if self._hi_card:
        self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()

      card.role = ((card.role or "") + " card-highlight").strip()
      self._hi_card = card

    self._selected_idx = idx

  def _load_up_to_index(self, target_idx):
    """Load all cards up to target index immediately"""
    while self._cards_loaded <= target_idx and self._cards_loaded < self._total_cards:
      # Load in larger batches for map clicks (faster)
      batch_size = min(50, target_idx - self._cards_loaded + 20)
      print(f"  Loading batch of {batch_size}...")

      if not self.load_next_page(n_rows=batch_size, silent=False):
        break  # No more data

  def _unselect_all(self):
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = []
      self.project_map.figure = fig

    if self._hi_card:
      self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      self._hi_card = None

    self._selected_idx = None

  def project_map_click(self, points, **event_args):
    if not points:
      self._unselect_all()
      return

    idx = points[0]["point_number"]

    if self._selected_idx == idx:
      self._unselect_all()
    else:
      self._select_index(idx)