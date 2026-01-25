from ._anvil_designer import projects_explorerTemplate
from anvil import *
import m3.components as m3
import plotly.graph_objects as go
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.js
from .. import Global


class projects_explorer(projects_explorerTemplate):
  def __init__(self, **properties):
    # Set form properties and data bindings
    self.init_components(**properties)
    self._hi_card = None
    self._selected_idx = None

    # Don't load data here - let the form_show or filter change event handle it
    # This prevents initial loading before user interaction

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
    self.filter_timer.interval = 1  # 300ms

  def apply_filters(self):
    """Apply filters and update map + cards with ONE server call"""
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

    # SINGLE SERVER CALL - gets both map and cards at once
    print("Fetching map and card data...")
    all_data = Global.project_explorer_data
    print("Data received, updating UI...")

    # Update map
    self.project_map.data = [all_data['map_data']]

    # Update project cards
    self.project_cards.items = all_data['project_cards']

    print("Map and cards updated!")

  def filter_timer_tick(self, **event_args):
    """This method is called when the timer fires"""
    self.filter_timer.interval = 0  # Stop the timer
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

  # ============ MAP CLICK EVENTS ============
  def _select_index(self, idx: int):
    """Highlight point idx on the map and the matching card."""
    # Map: select just this point
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = [idx]
      self.project_map.figure = fig

    # Card: scroll + highlight
    rows = self.project_cards.get_components()
    if 0 <= idx < len(rows):
      row = rows[idx]
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

  # ============ OTHER EVENTS ============
  def load_more_button_click(self, **event_args):
    """This method is called when the component is clicked."""
    pass
