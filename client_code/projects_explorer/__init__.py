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
    self.init_components(**properties)
    self._hi_card = None
    self._selected_idx = None

    # Pagination state
    self._current_page = 1
    self._page_size = 8
    self._total_count = 0
    self._total_pages = 0

    # Prevent double-loading on init
    self._initialized = False
    self._filters_ready = False

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    if self._initialized:
      return  # Prevent double-loading

    self.layout.reset_links()
    self.layout.projects_nav.role = 'selected'

    # Configure map appearance
    self.project_map.layout.map = dict(center=dict(lat=57, lon=-97), zoom=2, style="carto-voyager")
    self.project_map.layout.template = "mykonos_light"
    self.project_map.layout.margin = dict(t=5, b=5, l=5, r=5)

    # Hide pagination initially
    self.pagination_container.visible = False

    # Mark as ready to apply filters
    self._filters_ready = True
    self._initialized = True

    # Load initial data
    self.apply_filters()

  # ============ FILTER FUNCTIONS ============
  def schedule_filter_update(self):
    """Schedule a filter update with debouncing - waits 300ms after last change"""
    if not self._filters_ready:
      return  # Don't trigger during initialization
    self.filter_timer.interval = 0.3

  def apply_filters(self, page=None):
    """Apply filters and update map + cards with ONE server call"""
    if page is None:
      # Filter changed - reset to page 1
      self._current_page = 1
    else:
      # Specific page requested
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

    # UPDATE CHIPS - Build chip data from selections
    chips = []
    
    if provinces:
      for p in provinces:
        chips.append({'text': f'Province: {p}', 'tag': ('provinces', p)})
    
    if proj_types:
      for pt in proj_types:
        chips.append({'text': f'Project Type: {pt}', 'tag': ('proj_types', pt)})
    
    if stages:
      for s in stages:
        chips.append({'text': f'Stage: {s}', 'tag': ('stages', s)})
    
    if indigenous_ownership:
      for io in indigenous_ownership:
        chips.append({'text': f'Indigenous: {io}', 'tag': ('indigenous_ownership', io)})
    
    if project_scale:
      for ps in project_scale:
        chips.append({'text': f'Scale: {ps}', 'tag': ('project_scale', ps)})
    
    # Update the repeating panel
    self.filter_chips_panel.items = chips

    # Add pagination parameters
    kwargs["page"] = self._current_page
    kwargs["page_size"] = self._page_size

    # SINGLE SERVER CALL
    all_data = Global.project_explorer_data

    # Update map (always show all filtered points)
    self.project_map.data = [all_data['map_data']]

    # Update project cards (replace with current page)
    self.project_cards.items = all_data['project_cards']

    # Update pagination state
    self._total_count = all_data['total_count']
    self._total_pages = (self._total_count + self._page_size - 1) // self._page_size

    # Update pagination UI
    self._update_pagination_ui()

  def remove_filter(self, filter_type, value):
    """Remove a specific filter value and refresh"""
    # Remove the value from the appropriate dropdown
    if filter_type == 'provinces':
      current = list(self.provinces_dd.selected)
      current.remove(value)
      self.provinces_dd.selected = current
    elif filter_type == 'proj_types':
      current = list(self.proj_types_dd.selected)
      current.remove(value)
      self.proj_types_dd.selected = current
    elif filter_type == 'stages':
      current = list(self.stages_dd.selected)
      current.remove(value)
      self.stages_dd.selected = current
    elif filter_type == 'indigenous_ownership':
      current = list(self.indig_owners_dd.selected)
      current.remove(value)
      self.indig_owners_dd.selected = current
    elif filter_type == 'project_scale':
      current = list(self.project_scale_dd.selected)
      current.remove(value)
      self.project_scale_dd.selected = current
  
    # Schedule update with debouncing
    self.schedule_filter_update()

  def filter_timer_tick(self, **event_args):
    """This method is called when the timer fires"""
    self.filter_timer.interval = 0  # Stop the timer
    self.apply_filters()

  # ============ PAGINATION UI ============
  def _update_pagination_ui(self):
    """Update pagination buttons and info"""
    if self._total_pages <= 1:
      self.pagination_container.visible = False
      return

    self.pagination_container.visible = True

    # Update info label
    start = (self._current_page - 1) * self._page_size + 1
    end = min(self._current_page * self._page_size, self._total_count)
    self.page_info_label.text = f"Showing {start}-{end} of {self._total_count} projects"

    # Update page number label
    self.current_page_label.text = f"Page {self._current_page} of {self._total_pages}"

    # Enable/disable navigation buttons
    self.first_page_btn.enabled = self._current_page > 1
    self.prev_page_btn.enabled = self._current_page > 1
    self.next_page_btn.enabled = self._current_page < self._total_pages
    self.last_page_btn.enabled = self._current_page < self._total_pages

  def first_page_btn_click(self, **event_args):
    """Go to first page"""
    if self._current_page != 1:
      self.apply_filters(page=1)

  def prev_page_btn_click(self, **event_args):
    """Go to previous page"""
    if self._current_page > 1:
      self.apply_filters(page=self._current_page - 1)

  def next_page_btn_click(self, **event_args):
    """Go to next page"""
    if self._current_page < self._total_pages:
      self.apply_filters(page=self._current_page + 1)

  def last_page_btn_click(self, **event_args):
    """Go to last page"""
    if self._current_page != self._total_pages:
      self.apply_filters(page=self._total_pages)

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

    # Calculate which page this card is on
    target_page = (idx // self._page_size) + 1

    # If not on the right page, load it
    if target_page != self._current_page:
      self.apply_filters(page=target_page)

    # Calculate card index within the current page
    start_idx = (self._current_page - 1) * self._page_size
    card_idx = idx - start_idx

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

  def project_map_click(self, points, **event_args):
    """Handle map click events - jump directly to the page"""
    if not points:
      # Clicked empty area - unselect
      self._unselect_all()
      return

    idx = points[0]["point_number"]

    # Toggle: if clicking same point, unselect
    if self._selected_idx == idx:
      self._unselect_all()
      return

    # Select (will load correct page if needed)
    self._select_index(idx)
