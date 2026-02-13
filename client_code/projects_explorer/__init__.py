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
    # Set form properties and data bindings
    self.init_components(**properties)
    self._hi_card = None
    self._selected_idx = None
    self._current_filters = {}
    self._figures_loaded_up_to = 0  # Track how many cards have figures

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.projects_nav.role = 'selected'

    # Configure map appearance
    self.project_map.layout.map = dict(center=dict(lat=57, lon=-97), zoom=2, style="carto-voyager")
    self.project_map.layout.template = "mykonos_light"
    self.project_map.layout.margin = dict(t=5, b=5, l=5, r=5)

    # Load initial data when form is shown
    self.apply_filters()

  # ============ FILTER FUNCTIONS ============
  def schedule_filter_update(self):
    """Schedule a filter update with debouncing - waits 300ms after last change"""
    self.filter_timer.interval = 1

  def apply_filters(self):
    """Apply filters and update map + ALL cards (figures for first 15 only)"""
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

    # Store current filters for on-demand loading
    self._current_filters = kwargs

    # SERVER CALL - gets map and ALL cards (figures only for first 15)
    print("Fetching map and all cards...")
    all_data = anvil.server.call('get_all_map_and_cards', prebuild_limit=15, **kwargs)
    print("Data received, updating UI...")

    # Update map (shows all points)
    self.project_map.data = [all_data['map_data']]

    # Load ALL cards (figures only for first 15)
    self.project_cards.items = all_data['project_cards']

    # Track how many have figures
    self._figures_loaded_up_to = all_data['prebuilt_count']
    total_cards = all_data['total_count']

    # Show/hide and update load more button
    if self._figures_loaded_up_to < total_cards:
      self.load_more_button.visible = True
      remaining = total_cards - self._figures_loaded_up_to
      self.load_more_button.text = f"Load More Charts ({remaining} remaining)"
    else:
      self.load_more_button.visible = False

    print(f"Loaded ALL {total_cards} cards ({self._figures_loaded_up_to} with figures)")

  def filter_timer_tick(self, **event_args):
    """This method is called when the timer fires"""
    self.filter_timer.interval = 0
    self.apply_filters()

  # ============ DROPDOWN CHANGE EVENTS ============
  def provinces_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.schedule_filter_update()

  def proj_types_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.schedule_filter_update()

  def stages_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.schedule_filter_update()

  def indig_owners_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.schedule_filter_update()

  def project_scale_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.schedule_filter_update()

  # ============ LOAD MORE BUTTON ============
  def load_more_button_click(self, **event_args):
    """Load next batch of chart figures"""
    batch_size = 20  # Load 20 more at a time

    print(f"Loading more figures from index {self._figures_loaded_up_to}...")

    # Get current cards
    all_cards = list(self.project_cards.items)
    total_cards = len(all_cards)

    # Determine which cards need figures
    start_idx = self._figures_loaded_up_to
    end_idx = min(start_idx + batch_size, total_cards)

    # Load figures for this batch
    for i in range(start_idx, end_idx):
      card_data = all_cards[i]
      record_id = card_data.get('record_id')

      # Skip if already has figures
      if card_data.get('ownership_figure') or card_data.get('capital_mix_figure'):
        continue

      try:
        # Build figures for this card
        figures = anvil.server.call(
          'build_card_figures',
          record_id,
          **self._current_filters
        )

        if figures:
          # Update the card data
          card_data['ownership_figure'] = figures.get('ownership_figure')
          card_data['capital_mix_figure'] = figures.get('capital_mix_figure')

          print(f"Loaded figures for card {i+1}/{total_cards}")
      except Exception as e:
        print(f"Error loading figures for card {record_id}: {e}")

    # Refresh the repeating panel to show new figures
    self.project_cards.items = all_cards

    # Update tracking
    self._figures_loaded_up_to = end_idx

    # Update button
    if self._figures_loaded_up_to < total_cards:
      remaining = total_cards - self._figures_loaded_up_to
      self.load_more_button.text = f"Load More Charts ({remaining} remaining)"
    else:
      self.load_more_button.visible = False

    print(f"Figures loaded up to card {self._figures_loaded_up_to} of {total_cards}")

  # ============ MAP CLICK EVENTS ============
  def _select_index(self, idx: int):
    """Highlight point idx on the map and the matching card."""
    print(f"\n🎯 Selecting index {idx}")

    # Map: select just this point
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = [idx]
      self.project_map.figure = fig

    # Card: scroll + highlight
    rows = self.project_cards.get_components()
    if 0 <= idx < len(rows):
      row = rows[idx]
      card = row.project_card

      print(f"  - Found card for index {idx}")
      print(f"  - Card has load_figures_if_needed: {hasattr(card, 'load_figures_if_needed')}")

      row.scroll_into_view()

      # Clear previous highlight
      if self._hi_card:
        self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()

      card.role = ((card.role or "") + " card-highlight").strip()
      self._hi_card = card

      # Load figures on-demand if not already loaded
      if hasattr(card, 'load_figures_if_needed'):
        print(f"  - Calling load_figures_if_needed for card {idx}")
        card.load_figures_if_needed(self._current_filters)
      else:
        print(f"  ⚠️ Card doesn't have load_figures_if_needed method")

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

  def project_map_click(self, points, **event_args):
    """Handle map click events"""
    if not points:
      # Clicked empty area - unselect
      self._unselect_all()
      return

    idx = points[0]["point_number"]

    # Toggle: if clicking same point, unselect
    if self._selected_idx == idx:
      self._unselect_all()
    else:
      self._select_index(idx)