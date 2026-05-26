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

  # ==================== INITIALISATION ====================

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

    self._setup_dropdown_formatters()

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    if self._initialized:
      return

    self.layout.reset_links()
    self.layout.projects_nav.role = 'selected'

    self.project_map.layout.map = dict(center=dict(lat=57, lon=-97), zoom=2, style="carto-voyager")
    self.project_map.layout.template = "mykonos_light"
    self.project_map.layout.margin = dict(t=5, b=5, l=5, r=5)

    self.pagination_container.visible = False

    self._filters_ready = True
    self._initialized = True

    self.apply_filters()

  # ==================== DROPDOWN SETUP ====================

  def _setup_dropdown_formatters(self):
    """Make every multi-select always show its placeholder, never 'N items selected'"""
    for dd in (
      self.provinces_dd,
      self.proj_types_dd,
      self.stages_dd,
      self.indig_owners_dd,
      self.project_scale_dd,
    ):
      def make_formatter(label):
        def format_selected_text(count, total):
          return label
        return format_selected_text
      dd.format_selected_text = make_formatter(dd.placeholder)

  # ==================== FILTER MANAGEMENT ====================

  def schedule_filter_update(self):
    """Schedule a filter update with debouncing - waits 300ms after last change"""
    if not self._filters_ready:
      return
    self.filter_timer.interval = 0.3

  def filter_timer_tick(self, **event_args):
    self.filter_timer.interval = 0
    self.apply_filters()

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

  def remove_filter(self, filter_type, value):
    """Remove a specific filter value and refresh"""
    targets = {
      'provinces':            self.provinces_dd,
      'proj_types':           self.proj_types_dd,
      'stages':               self.stages_dd,
      'indigenous_ownership': self.indig_owners_dd,
      'project_scale':        self.project_scale_dd,
    }
    if filter_type in targets:
      current = list(targets[filter_type].selected)
      current.remove(value)
      targets[filter_type].selected = current
    self.schedule_filter_update()

  # ==================== FILTER HELPERS ====================

  def _get_filter_kwargs(self):
    kwargs = {}
    if self.provinces_dd.selected:
      kwargs['provinces'] = self.provinces_dd.selected
    if self.proj_types_dd.selected:
      kwargs['proj_types'] = self.proj_types_dd.selected
    if self.stages_dd.selected:
      kwargs['stages'] = self.stages_dd.selected
    if self.indig_owners_dd.selected:
      INDIG_MAP = {
        'Majority owned (51-100%)': [
          'Wholly Indigenous owned (100%)',
          'Majority Indigenous owned (51-99%)',
        ],
        'Minority owned (1-50%)': [
          'Half Indigenous owned (50%)',
          'Minority Indigenous owned (1-49%)',
        ],
        'No Indigenous ownership': ['No Indigenous ownership'],
      }
      expanded = []
      for selection in self.indig_owners_dd.selected:
        expanded.extend(INDIG_MAP.get(selection, [selection]))
      kwargs['indigenous_ownership'] = expanded
    if self.project_scale_dd.selected:
      kwargs['project_scale'] = self.project_scale_dd.selected
    return kwargs

  def _get_active_filters(self):
    """Returns human-readable filter labels for export annotations."""
    def fmt(selected):
      return ", ".join(selected) if selected else "All"
    return {
      "Provinces":     fmt(self.provinces_dd.selected),
      "Project Types": fmt(self.proj_types_dd.selected),
      "Stages":        fmt(self.stages_dd.selected),
      "Indigenous":    fmt(self.indig_owners_dd.selected),
      "Project Scale": fmt(self.project_scale_dd.selected),
    }

  def _build_filter_chips(self):
    """Build chip data from current filter selections for the repeating panel."""
    chips = []
    mappings = [
      (self.provinces_dd.selected,    'provinces',            'Province'),
      (self.proj_types_dd.selected,   'proj_types',           'Technology'),
      (self.stages_dd.selected,       'stages',               'Stage'),
      (self.indig_owners_dd.selected, 'indigenous_ownership', 'Indigenous Ownership'),
      (self.project_scale_dd.selected,'project_scale',        'Scale'),
    ]
    for selected, filter_type, label in mappings:
      for value in (selected or []):
        chips.append({'text': f'{label}: {value}', 'tag': (filter_type, value)})
    return chips

  # ==================== APPLY FILTERS ====================

  def apply_filters(self, page=None):
    """Apply filters and update map + cards with ONE server call"""
    if page is None:
      self._current_page = 1
    else:
      self._current_page = page

    self.filter_chips_panel.items = self._build_filter_chips()

    kwargs = self._get_filter_kwargs()
    kwargs['page'] = self._current_page
    kwargs['page_size'] = self._page_size

    all_data = anvil.server.call('get_all_map_and_cards', **kwargs)

    self.project_map.data = all_data['map_data']

    self._sub_parent_map     = all_data.get('sub_parent_map', {})
    self._sub_id_to_point    = all_data.get('sub_id_to_point', {})
    self._parent_to_sub_points = all_data.get('parent_to_sub_points', {})
    self._point_coords       = all_data.get('point_coords', {})
    self._sub_point_coords   = all_data.get('sub_point_coords', {})

    self.project_cards.items = all_data['project_cards']

    self._total_count  = all_data['total_count']
    self._total_pages  = (self._total_count + self._page_size - 1) // self._page_size

    self._update_pagination_ui()

  # ==================== PAGINATION ====================

  def _update_pagination_ui(self):
    """Update pagination buttons and info"""
    if self._total_pages <= 1:
      self.pagination_container.visible = False
      return

    self.pagination_container.visible = True

    start = (self._current_page - 1) * self._page_size + 1
    end   = min(self._current_page * self._page_size, self._total_count)
    self.page_info_label.text    = f"Showing {start}-{end} of {self._total_count}"
    self.current_page_label.text = f"Page {self._current_page} of {self._total_pages}"

    self.first_page_btn.enabled = self._current_page > 1
    self.prev_page_btn.enabled  = self._current_page > 1
    self.next_page_btn.enabled  = self._current_page < self._total_pages
    self.last_page_btn.enabled  = self._current_page < self._total_pages

  def _scroll_to_first_card(self):
    rows = self.project_cards.get_components()
    if rows:
      anvil.js.call_js('smoothScroll', anvil.js.get_dom_node(rows[0]))

  def first_page_btn_click(self, **event_args):
    if self._current_page != 1:
      self.apply_filters(page=1)
      self._scroll_to_first_card()

  def prev_page_btn_click(self, **event_args):
    if self._current_page > 1:
      self.apply_filters(page=self._current_page - 1)
      self._scroll_to_first_card()

  def next_page_btn_click(self, **event_args):
    if self._current_page < self._total_pages:
      self.apply_filters(page=self._current_page + 1)
      self._scroll_to_first_card()

  def last_page_btn_click(self, **event_args):
    if self._current_page != self._total_pages:
      self.apply_filters(page=self._total_pages)
      self._scroll_to_first_card()

  # ==================== MAP CLICK EVENTS ====================

  def _select_index(self, idx: int):
    """Highlight point idx on the map and the matching card."""
    # --- (3) clear previous highlight safely, before anything gets rebuilt ---
    self._clear_card_highlight()

    # --- (2) navigate FIRST so the map data + cards are rebuilt ---
    target_page = (idx // self._page_size) + 1
    if target_page != self._current_page:
      self.apply_filters(page=target_page)

    # --- (2) NOW set the selection, so it survives the data rebuild ---
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = [idx]
      sub_points = self._parent_to_sub_points.get(str(idx), [])
      if len(fig.data) > 1:
        fig.data[1].selectedpoints = sub_points

      if sub_points and self._sub_point_coords:
        sub_coords = [self._sub_point_coords[str(sp)] for sp in sub_points if str(sp) in self._sub_point_coords]
        if sub_coords:
          avg_lat = sum(c["lat"] for c in sub_coords) / len(sub_coords)
          avg_lon = sum(c["lon"] for c in sub_coords) / len(sub_coords)
          fig.layout.map.center = dict(lat=avg_lat, lon=avg_lon)
          fig.layout.map.zoom = 3        # (1) was 4
      else:
        coords = self._point_coords.get(str(idx))
        if coords and coords["lat"] != 0 and coords["lon"] != 0:
          fig.layout.map.center = dict(lat=coords["lat"], lon=coords["lon"])
          fig.layout.map.zoom = 3.5      # (1) was 5
      self.project_map.figure = fig

    # --- (3) highlight the card on the now-current page ---
    start_idx = (self._current_page - 1) * self._page_size
    card_idx  = idx - start_idx
    rows = self.project_cards.get_components()
    if 0 <= card_idx < len(rows):
      row = rows[card_idx]
      row.project_card.role = ((row.project_card.role or "") + " card-highlight").strip()
      self._hi_card = row.project_card
      self._hi_row  = row
      anvil.js.call_js('smoothScroll', anvil.js.get_dom_node(row))   # scroll last

    self._selected_idx = idx

  def _clear_card_highlight(self):
    if self._hi_card:
      try:
        self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      except Exception:
        pass
      self._hi_card = None
    if self._hi_row and hasattr(self._hi_row, 'clear_sub_highlight'):
      try:
        self._hi_row.clear_sub_highlight()
      except Exception:
        pass
      self._hi_row = None

  def _unselect_all(self):
    """Clear selection from both map and cards."""
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = []
      if len(fig.data) > 1:
        fig.data[1].selectedpoints = []
      fig.layout.map.center = dict(lat=57, lon=-97)
      fig.layout.map.zoom = 2
      self.project_map.figure = fig

    if self._hi_card:
      self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      self._hi_card = None
    if self._hi_row and hasattr(self._hi_row, 'clear_sub_highlight'):
      self._hi_row.clear_sub_highlight()
      self._hi_row = None

    self._selected_idx     = None
    self._selected_sub_id  = None

  def project_map_click(self, points, **event_args):
    if not points:
      self._unselect_all()
      return

    pt    = points[0]
    curve = pt.get("curve_number", 0)
    idx   = pt["point_number"]

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
    point_idx = self._sub_id_to_point.get(sub_id)
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = [parent_pos]
      if len(fig.data) > 1:
        fig.data[1].selectedpoints = [point_idx] if point_idx is not None else []

      if point_idx is not None:
        coords = self._sub_point_coords.get(str(point_idx))
        if coords:
          fig.layout.map.center = dict(lat=coords["lat"], lon=coords["lon"])
          fig.layout.map.zoom = 6

      self.project_map.figure = fig

    target_page = (parent_pos // self._page_size) + 1
    if target_page != self._current_page:
      self.apply_filters(page=target_page)

    start_idx = (self._current_page - 1) * self._page_size
    card_idx  = parent_pos - start_idx
    rows = self.project_cards.get_components()
    if 0 <= card_idx < len(rows):
      row = rows[card_idx]

      if self._hi_card:
        self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      if self._hi_row and hasattr(self._hi_row, 'clear_sub_highlight'):
        self._hi_row.clear_sub_highlight()

      row.project_card.role = ((row.project_card.role or "") + " card-highlight").strip()
      self._hi_card = row.project_card
      self._hi_row  = row

      subs = row.item.get("sub_projects", [])
      if subs:
        selected  = [s for s in subs if s.get("sub_id") == sub_id]
        others    = [s for s in subs if s.get("sub_id") != sub_id]
        reordered = selected + others

        if len(subs) <= 5:
          row.sub_projects_list.items   = reordered
          row.sub_projects_list.visible = True
          row._showing_all              = True
          row.sub_projects_label.text   = f"Portfolio · {len(subs)} sub-projects ▴"
          row.show_more_link.visible    = False
        else:
          row.sub_projects_list.items   = reordered[:5]
          row.sub_projects_list.visible = True
          row._showing_all              = False
          row.sub_projects_label.text   = f"Portfolio · showing 5 of {len(subs)} ▾"
          row.show_more_link.text       = f"Show all {len(subs)} sub-projects"
          row.show_more_link.visible    = True

      row.highlight_sub_row(sub_id)

      if scroll:
        anvil.js.call_js('smoothScroll', anvil.js.get_dom_node(row))

    self._selected_idx    = parent_pos
    self._selected_sub_id = sub_id