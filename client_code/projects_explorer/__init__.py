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
    self._hi_row = None
    self._selected_idx = None

    self._handling_sub_click = False

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
    all_data = anvil.server.call('get_all_map_and_cards', **kwargs)

    self.project_map.data = all_data['map_data']
    
    # Store sub-project → parent mapping for click handling
    self._sub_parent_map = all_data.get('sub_parent_map', {})
    self._sub_id_to_point = all_data.get('sub_id_to_point', {})
    self._parent_to_sub_points = all_data.get('parent_to_sub_points', {})

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
    self.page_info_label.text = f"Showing {start}-{end} of {self._total_count}"

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
  def _select_index(self, idx: int, sub_id=None):
    """Highlight point idx on the map and the matching card."""
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = [idx]
      if len(fig.data) > 1:
        sub_points = self._parent_to_sub_points.get(str(idx), [])
        fig.data[1].selectedpoints = sub_points

      # Zoom to the selected point
      lat = fig.data[0].lat[idx]
      lon = fig.data[0].lon[idx]
      fig.layout.map.center = dict(lat=lat, lon=lon)
      fig.layout.map.zoom = 6

      self.project_map.figure = fig
  
    target_page = (idx // self._page_size) + 1
  
    if target_page != self._current_page:
      self.apply_filters(page=target_page)
  
    start_idx = (self._current_page - 1) * self._page_size
    card_idx = idx - start_idx
  
    rows = self.project_cards.get_components()
    if 0 <= card_idx < len(rows):
      row = rows[card_idx]
      row.scroll_into_view()
  
      # Clear previous highlight
      if self._hi_card:
        self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      if self._hi_row and hasattr(self._hi_row, 'clear_sub_highlight'):
        self._hi_row.clear_sub_highlight()
  
        # Set new highlight
      row.project_card.role = ((row.project_card.role or "") + " card-highlight").strip()
      self._hi_card = row.project_card
      self._hi_row = row
  
    self._selected_idx = idx
    self._selected_sub_id = sub_id
  
  def _unselect_all(self):
    """Clear selection from both map and cards."""
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = []
      if len(fig.data) > 1:
        fig.data[1].selectedpoints = []
      # Reset zoom
      fig.layout.map.center = dict(lat=57, lon=-97)
      fig.layout.map.zoom = 2
      self.project_map.figure = fig

    if self._hi_card:
      self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      self._hi_card = None
    if self._hi_row and hasattr(self._hi_row, 'clear_sub_highlight'):
      self._hi_row.clear_sub_highlight()
      self._hi_row = None

    self._selected_idx = None
    self._selected_sub_id = None

  def project_map_click(self, points, **event_args):
    """Handle map click events"""
    if not points:
      self._unselect_all()
      return
  
    pt = points[0]
    curve = pt.get("curve_number", 0)
    idx = pt["point_number"]
  
    if curve == 0:
      if self._selected_idx == idx:
        self._unselect_all()
      else:
        self._select_index(idx)
  
    elif curve == 1:
      info = self._sub_parent_map.get(str(idx))
      if info:
        self._select_sub_project(info["parent_pos"], info["sub_id"], scroll=True)

  def _select_sub_project(self, parent_pos, sub_id, scroll=False):
    """Select a sub-project: highlight parent card, expand list, highlight row and map pin"""
    # === 1. Update map — BOTH traces in one write ===
    point_idx = self._sub_id_to_point.get(sub_id)
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = [parent_pos]
      if len(fig.data) > 1:
        fig.data[1].selectedpoints = [point_idx] if point_idx is not None else []

      # Zoom to the sub-project
      if point_idx is not None and len(fig.data) > 1:
        lat = fig.data[1].lat[point_idx]
        lon = fig.data[1].lon[point_idx]
        fig.layout.map.center = dict(lat=lat, lon=lon)
        fig.layout.map.zoom = 6

      self.project_map.figure = fig

    # === 2. Navigate to correct page ===
    target_page = (parent_pos // self._page_size) + 1
    if target_page != self._current_page:
      self.apply_filters(page=target_page)

    # === 3. Highlight parent card ===
    start_idx = (self._current_page - 1) * self._page_size
    card_idx = parent_pos - start_idx
    rows = self.project_cards.get_components()
    if 0 <= card_idx < len(rows):
      row = rows[card_idx]

      # Clear previous highlights
      if self._hi_card:
        self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      if self._hi_row and hasattr(self._hi_row, 'clear_sub_highlight'):
        self._hi_row.clear_sub_highlight()

      row.project_card.role = ((row.project_card.role or "") + " card-highlight").strip()
      self._hi_card = row.project_card
      self._hi_row = row

      # === 4. Expand list with selected sub-project at the top ===
      subs = row.item.get("sub_projects", [])
      if subs:
        selected = [s for s in subs if s.get("sub_id") == sub_id]
        others = [s for s in subs if s.get("sub_id") != sub_id]
        reordered = selected + others

        if len(subs) <= 5:
          row.sub_projects_list.items = reordered
          row.sub_projects_list.visible = True
          row._showing_all = True
          row.sub_projects_label.text = f"Portfolio · {len(subs)} sub-projects ▴"
          row.show_more_link.visible = False
        else:
          row.sub_projects_list.items = reordered[:5]
          row.sub_projects_list.visible = True
          row._showing_all = False
          row.sub_projects_label.text = f"Portfolio · showing 5 of {len(subs)} ▾"
          row.show_more_link.text = f"Show all {len(subs)} sub-projects"
          row.show_more_link.visible = True

      # === 5. Highlight the sub-project row ===
      row.highlight_sub_row(sub_id)

      # === 6. Scroll to the parent card (only from map clicks) ===
      if scroll:
        row.scroll_into_view()

    self._selected_idx = parent_pos
    self._selected_sub_id = sub_id