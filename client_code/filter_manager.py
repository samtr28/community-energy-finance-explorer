import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from anvil.js import window
from anvil_extras.MultiSelectDropDown import MultiSelectDropDown
from .filter_config import (FILTERS, OWNER_CATEGORY_ORDER, NARROW_SCREEN_PX,
                            DROPDOWN_PADDING_PX, DROPDOWN_MIN_WIDTH_PX,
                            SMALL_SAMPLE_WARNING_BELOW, MESSAGES)
from anvil import Notification
_measure_ctx = None


def _text_px(text, font="16px Arial"):
  """Rendered width of a label in px (falls back to a rough estimate)."""
  global _measure_ctx
  try:
    if _measure_ctx is None:
      _measure_ctx = window.document.createElement('canvas').getContext('2d')
    _measure_ctx.font = font
    return float(_measure_ctx.measureText(text).width)
  except Exception:
    return len(text) * 9.0
    
class FilterManager:
  """Builds the filter dropdowns into a FlowPanel and handles kwargs, chips and labels."""

  def __init__(self, panel, on_change, defaults=None, specs=FILTERS, project_privacy=False):
    self._specs = list(specs)
    self._on_change = on_change
    self._dds = {}
    self._defaults = {}
    self._panel = panel
    self._filters_btn = self._reset_btn = self._count_lbl = None
    self._chips_panel = self._chips_row = None

    # Values found in the data, for dropdowns marked items_from: 'data'
    self._present = {}
    if any(s.get('items_from') == 'data' for s in self._specs):
      self._present = anvil.server.call('get_filter_options', project_privacy)

    # Owner categories and subtypes, for dropdowns marked items_from: 'owner_options'
    self._owner_options = {}
    if any(s.get('items_from') == 'owner_options' for s in self._specs):
      self._owner_options = anvil.server.call('get_owner_type_options', project_privacy)

    for spec in self._specs:
      dd = MultiSelectDropDown(
        placeholder=spec['label'],
        multiple=True,
        items=self._items_for(spec),
        width=self._dropdown_width(spec['label']),
      )
      dd.format_selected_text = self._make_formatter(spec['label'])
      dd.set_event_handler('change', self._make_handler(spec['key']))
      panel.add_component(dd)
      self._dds[spec['key']] = dd

    # Pre-select defaults (skipping any value that is not in the dropdown)
    for key, selected in (defaults or {}).items():
      if key in self._dds:
        available = set(self._dds[key].items or [])
        pruned = [v for v in selected if v in available]
        self._dds[key].selected = pruned
        self._defaults[key] = pruned

  # ---------- layout ----------
  @staticmethod
  def _dropdown_width(label):
    """Width that fits the label text, never wider than the screen."""
    width = max(DROPDOWN_MIN_WIDTH_PX, _text_px(label) + DROPDOWN_PADDING_PX)
    width = min(width, window.innerWidth - 48)
    return f"{int(width)}px"

  # ---------- items ----------
  def _items_for(self, spec):
    if spec.get('items_from') == 'owner_options':
      if spec['key'] == 'owner_types':
        return self._subtype_items(selected_categories=None)
      return self._category_items()
    if spec.get('items_from') == 'data':
      return self._present.get(spec['key'], [])
    return spec['items']

  def _category_items(self):
    cats = list(self._owner_options)
    order = {c: i for i, c in enumerate(OWNER_CATEGORY_ORDER)}
    return sorted(cats, key=lambda c: (order.get(c, len(order)), c))

  def _subtype_items(self, selected_categories):
    cats = selected_categories or list(self._owner_options)
    return sorted({t for c in cats for t in self._owner_options.get(c, [])})

  def _refresh_subtypes(self):
    sub = self._dds.get('owner_types')
    cat = self._dds.get('owner_categories')
    if sub is None or cat is None:
      return
    items = self._subtype_items(list(cat.selected or []))
    keep = [v for v in (sub.selected or []) if v in items]
    sub.items = items
    sub.selected = keep

  # ---------- events ----------
  def _make_handler(self, key):
    def handler(**event_args):
      if key == 'owner_categories':
        self._refresh_subtypes()
      self._on_change()
    return handler

  @staticmethod
  def _make_formatter(label):
    def format_selected_text(count, total):
      return label
    return format_selected_text

  # ---------- what the page needs ----------
  def get_kwargs(self):
    kwargs = {}
    for spec in self._specs:
      selected = list(self._dds[spec['key']].selected or [])
      if not selected:
        continue
      expand = spec.get('expand')
      if expand:
        expanded = []
        for s in selected:
          expanded.extend(expand.get(s, [s]))
        selected = expanded
      kwargs[spec['key']] = selected
    return kwargs

  def get_active_labels(self):
    out = {}
    for spec in self._specs:
      selected = self._dds[spec['key']].selected
      out[spec['export']] = ", ".join(selected) if selected else "All"
    return out

  def _is_active(self, key):
    """True when a dropdown's selection differs from its default."""
    selected = set(self._dds[key].selected or [])
    return selected != set(self._defaults.get(key, []))

  def active_count(self):
    return sum(1 for spec in self._specs if self._dds[spec['key']].selected)

  def get_chips(self):
    """One chip per selected value, including the default selections."""
    chips = []
    for spec in self._specs:
      key = spec['key']
      for value in (self._dds[key].selected or []):
        chips.append({'text': f"{spec['chip']}: {value}", 'tag': (key, value)})
    return chips

  def remove(self, key, value):
    dd = self._dds[key]
    current = list(dd.selected or [])
    if value in current:
      current.remove(value)
    dd.selected = current
    if key == 'owner_categories':
      self._refresh_subtypes()
    self._on_change()

  def reset(self):
    """Clear every filter, including the default Scale selection."""
    for dd in self._dds.values():
      dd.selected = []
    self._refresh_subtypes()
    self._on_change()

  # ---------- toolbar (button, reset, count line, chips) ----------
  def attach_toolbar(self, filters_btn, reset_btn, count_lbl, chips_panel, chips_row):
    """Wire the page's toolbar components. Collapses the dropdowns on narrow screens."""
    self._filters_btn, self._reset_btn, self._count_lbl = filters_btn, reset_btn, count_lbl
    self._chips_panel, self._chips_row = chips_panel, chips_row
    filters_btn.set_event_handler('click', self._toggle_panel)
    reset_btn.set_event_handler('click', self._reset_clicked)
    self._panel.visible = window.innerWidth >= NARROW_SCREEN_PX
    self._update_button()

  def _toggle_panel(self, **event_args):
    self._panel.visible = not self._panel.visible
    self._update_button()

  def _reset_clicked(self, **event_args):
    self.reset()

  def _update_button(self):
    if self._filters_btn is None:
      return
    n = self.active_count()
    self._filters_btn.text = f"Filters ({n})" if n else "Filters"
    self._filters_btn.icon = 'mi:expand_less' if self._panel.visible else 'mi:expand_more'

  def refresh_ui(self):
    """Call before each server call: updates chips, their row, and the button."""
    chips = self.get_chips()
    if self._chips_panel is not None:
      self._chips_panel.items = chips
      self._chips_row.visible = bool(chips)
    self._update_button()

  def _excluded_notes(self):
    """One note per flagged filter that is only partly selected."""
    notes = []
    for spec in self._specs:
      if not spec.get('note_excluded'):
        continue
      dd = self._dds[spec['key']]
      selected = set(dd.selected or [])
      if not selected:
        continue                      # nothing selected = no filter = all included
      excluded = [i for i in (dd.items or []) if i not in selected]
      if not excluded:
        continue
      is_default = selected == set(self._defaults.get(spec['key'], []))
      template = MESSAGES['excluded_default'] if is_default else MESSAGES['excluded']
      notes.append(template.format(label=spec['chip'], items=", ".join(excluded)))
    return notes

  def show_count(self, charts, small_warning=True, note=None):
    """Call after each server call: writes the count/anonymity line."""
    if self._count_lbl is None:
      return
    if charts.get('no_results'):
      self._count_lbl.text = MESSAGES['hidden']
      return
    n = charts.get('project_count')
    if charts.get('anon_excluded'):
      parts = [MESSAGES['partial'].format(n=n, noun='project' if n == 1 else 'projects')]
    else:
      parts = [MESSAGES['count'].format(n=n, total=charts.get('total_projects'))]
    parts.extend(self._excluded_notes())
    if small_warning and n < SMALL_SAMPLE_WARNING_BELOW:
      parts.append(MESSAGES['small'])
    if note:
      parts.append(note)
    self._count_lbl.text = " ".join(parts)

  def show_loading(self):
    if self._count_lbl is not None:
      self._count_lbl.text = "Loading…"