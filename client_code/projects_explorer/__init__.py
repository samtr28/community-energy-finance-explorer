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

    # Map ↔ Card linking (populated by apply_filters)
    self._record_id_to_map_indices = {}   # str(record_id) -> [map point indices]
    self._map_point_record_ids = []       # map point index -> str(record_id)
    self._page_record_ids = []            # card index on page -> str(record_id)

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

    # Update map (all filtered points — portfolios exploded into individual pins)
    self.project_map.data = [all_data['map_data']]

    # Update project cards (one card per project/portfolio, paginated)
    self.project_cards.items = all_data['project_cards']

    # Store map ↔ card linking data
    self._record_id_to_map_indices = all_data.get('record_id_to_map_indices', {})
    self._map_point_record_ids = all_data.get('map_point_record_ids', [])
    self._page_record_ids = [
      str(card.get('record_id', '')) for card in all_data['project_cards']
    ]

    # Update pagination state
    self._total_count = all_data['total_count']
    self._total_pages = (self._total_count + self._page_size - 1) // self._page_size

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
    """Highlight all map pins belonging to a record_id (handles portfolios)."""
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
    rid_str = str(record_id)
    if rid_str not in self._page_record_ids:
      return False

    card_idx = self._page_record_ids.index(rid_str)

    rows = self.project_cards.get_components()
    if 0 <= card_idx < len(rows):
      row = rows[card_idx]
      row.scroll_into_view()
      row.project_card.role = ((row.project_card.role or "") + " card-highlight").strip()
      self._hi_card = row.project_card

    return True

  def _select_by_record_id(self, record_id):
    """Select a project by record_id: highlight its map pins and card."""
    self._highlight_map_pins(record_id)
    self._highlight_card(record_id)
    self._selected_record_id = str(record_id)

  def _unselect_all(self):
    """Clear selection from both map and cards."""
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = []
      self.project_map.figure = fig

    if self._hi_card:
      self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      self._hi_card = None

    self._selected_record_id = None

  # ============ MAP CLICK EVENTS ============
  def project_map_click(self, points, **event_args):
    """Handle map click events.
    Uses point_number (always reliable in Anvil) to look up record_id,
    then highlights all pins for that project and scrolls to the card."""
    if not points:
      self._unselect_all()
      return

    # Get point_number — this always works in Anvil's plotly
    point_number = points[0].get("point_number")
    if point_number is None:
      self._unselect_all()
      return

    # Look up record_id from the flat list
    if point_number < 0 or point_number >= len(self._map_point_record_ids):
      self._unselect_all()
      return

    record_id = self._map_point_record_ids[point_number]

    # Toggle: if clicking same project, unselect
    if self._selected_record_id == record_id:
      self._unselect_all()
      return

    # Select by record_id (highlights all portfolio pins + scrolls to card)
    self._select_by_record_id(record_id)