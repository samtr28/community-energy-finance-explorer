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
    self._selected_record_id = None

    # Pagination state
    self._current_page = 1
    self._page_size = 8
    self._total_count = 0
    self._total_pages = 0

    # Map ↔ Card linking
    # Maps record_id -> list of map point indices (for highlighting all portfolio pins)
    self._record_id_to_map_indices = {}
    # Maps record_id -> card index within current page (for scrolling to card)
    self._page_record_ids = []

    # Prevent double-loading on init
    self._initialized = False
    self._filters_ready = False

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    if self._initialized:
      return

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
      return
    self.filter_timer.interval = 0.3

  def apply_filters(self, page=None):
    """Apply filters and update map + cards with ONE server call"""
    if page is None:
      self._current_page = 1
    else:
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

    # UPDATE CHIPS
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

    self.filter_chips_panel.items = chips

    # Add pagination parameters
    kwargs["page"] = self._current_page
    kwargs["page_size"] = self._page_size

    # SINGLE SERVER CALL
    all_data = anvil.server.call('get_all_map_and_cards', **kwargs)

    # Update map (all filtered points, portfolios exploded into individual pins)
    self.project_map.data = [all_data['map_data']]

    # Update project cards (one card per project/portfolio, paginated)
    self.project_cards.items = all_data['project_cards']

    # Store map ↔ card linking data
    self._record_id_to_map_indices = all_data.get('record_id_to_map_indices', {})

    # Build list of record_ids for the current page of cards
    self._page_record_ids = [
      card.get('record_id') for card in all_data['project_cards']
    ]

    # Update pagination state
    self._total_count = all_data['total_count']
    self._total_pages = (self._total_count + self._page_size - 1) // self._page_size

    # Update pagination UI
    self._update_pagination_ui()

    # Clear any previous selection
    self._selected_record_id = None
    self._hi_card = None

  def remove_filter(self, filter_type, value):
    """Remove a specific filter value and refresh"""
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

    self.schedule_filter_update()

  def filter_timer_tick(self, **event_args):
    """This method is called when the timer fires"""
    self.filter_timer.interval = 0
    self.apply_filters()

  # ============ PAGINATION UI ============
  def _update_pagination_ui(self):
    """Update pagination buttons and info"""
    if self._total_pages <= 1:
      self.pagination_container.visible = False
      return

    self.pagination_container.visible = True

    start = (self._current_page - 1) * self._page_size + 1
    end = min(self._current_page * self._page_size, self._total_count)
    self.page_info_label.text = f"Showing {start}-{end} of {self._total_count} projects"
    self.current_page_label.text = f"Page {self._current_page} of {self._total_pages}"

    self.first_page_btn.enabled = self._current_page > 1
    self.prev_page_btn.enabled = self._current_page > 1
    self.next_page_btn.enabled = self._current_page < self._total_pages
    self.last_page_btn.enabled = self._current_page < self._total_pages

  def first_page_btn_click(self, **event_args):
    if self._current_page != 1:
      self.apply_filters(page=1)

  def prev_page_btn_click(self, **event_args):
    if self._current_page > 1:
      self.apply_filters(page=self._current_page - 1)

  def next_page_btn_click(self, **event_args):
    if self._current_page < self._total_pages:
      self.apply_filters(page=self._current_page + 1)

  def last_page_btn_click(self, **event_args):
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

  # ============ SELECTION HELPERS ============
  def _highlight_map_pins(self, record_id):
    """Highlight all map pins belonging to a record_id."""
    fig = self.project_map.figure
    if not fig or not fig.data:
      return
  
    indices = self._record_id_to_map_indices.get(str(record_id), [])
    fig.data[0].selectedpoints = indices
    self.project_map.figure = fig

  def _highlight_card(self, record_id):
    """Scroll to and highlight the card matching record_id on the current page."""
    # Clear previous highlight
    if self._hi_card:
      self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      self._hi_card = None

    # Find the card index on the current page
    try:
      card_idx = self._page_record_ids.index(record_id)
    except ValueError:
      # record_id not on current page — need to find which page it's on
      return False

    rows = self.project_cards.get_components()
    if 0 <= card_idx < len(rows):
      row = rows[card_idx]
      row.scroll_into_view()
      row.project_card.role = ((row.project_card.role or "") + " card-highlight").strip()
      self._hi_card = row.project_card

    return True

  def _find_page_for_record_id(self, record_id):
    """Determine which page a record_id is on.
    Returns page number or None if not found.
    
    NOTE: This requires the server to provide ordered record_ids,
    or a separate server call. For now, returns None and the caller
    can decide whether to make an additional server call."""
    # Since cards are filtered and paginated server-side, we don't have
    # the full filtered list client-side. If the record_id is not on the
    # current page, we can't know which page it's on without asking the server.
    # For most use cases (clicking a map pin), the card will be on the current page
    # or the user will navigate to it.
    return None

  def _select_by_record_id(self, record_id):
    """Select a project by record_id: highlight its map pins and card."""
    # Highlight all map pins for this record_id (handles portfolios)
    self._highlight_map_pins(record_id)

    # Try to highlight the card on the current page
    found = self._highlight_card(record_id)

    if not found:
      # Card is on a different page — we could load it, but for now
      # just highlight the map pins. The user can navigate pages.
      pass

    self._selected_record_id = record_id

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

    self._selected_record_id = None

  # ============ MAP CLICK EVENTS ============
  def project_map_click(self, points, **event_args):
    """Handle map click events.
    Clicking a pin highlights all pins for that project/portfolio
    and scrolls to the matching card."""
    if not points:
      self._unselect_all()
      return

    # Extract record_id from customdata [community, record_id]
    customdata = points[0].get("customdata", [])
    if len(customdata) < 2:
      self._unselect_all()
      return

    record_id = customdata[1]

    # Toggle: if clicking same project, unselect
    if self._selected_record_id == record_id:
      self._unselect_all()
      return

    # Select by record_id (highlights all portfolio pins + scrolls to card)
    self._select_by_record_id(record_id)