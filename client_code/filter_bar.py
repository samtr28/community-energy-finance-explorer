import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from anvil import FlowPanel, Label, Timer
import m3.components as m3
from anvil_extras.Chip import Chip
from .filter_manager import FilterManager
from .filter_config import FILTER_DEBOUNCE_SECONDS


def _text(text=""):
  """Theme text if available, otherwise a plain label."""
  try:
    return m3.Text(text=text, scale='small')
  except Exception:
    return Label(text=text, font_size=13)


class _ChipRow:
  """Stands in for a RepeatingPanel: setting .items rebuilds the chips."""

  def __init__(self, flow_panel, on_remove):
    self._flow = flow_panel
    self._on_remove = on_remove
    self._items = []

  def _remover(self, key, value):
    def handler(**event_args):
      self._on_remove(key, value)
    return handler

  @property
  def items(self):
    return self._items

  @items.setter
  def items(self, chips):
    self._items = list(chips)
    self._flow.clear()
    for item in self._items:
      key, value = item['tag']
      chip = Chip(text=item['text'],
                  background='theme:Primary Container',
                  foreground='theme:On Primary Container',
                  spacing_above='none', spacing_below='none')
      chip.set_event_handler('close_click', self._remover(key, value))
      self._flow.add_component(chip)


def build_filter_bar(host, on_apply, defaults=None, project_privacy=False):
  """
  Build the whole filter UI (toolbar, dropdowns, chips, count line) inside `host`,
  an empty LinearPanel on the page. `on_apply` is called after a short debounce
  whenever a filter changes. Returns the FilterManager that drives it.
  """
  toolbar     = FlowPanel(vertical_align='bottom')
  filters_btn = m3.Button(text='Filters', icon='mi:tune')
  reset_btn   = m3.Button(text='Clear all', appearance='outlined')
  count_lbl   = _text()
  for c in (filters_btn, reset_btn, count_lbl):
    toolbar.add_component(c)

  dropdown_panel = FlowPanel(gap='tiny')

  chips_row  = FlowPanel(vertical_align='middle')
  chips_flow = FlowPanel(gap='tiny')
  chips_row.add_component(_text('Selected:'))
  chips_row.add_component(chips_flow)

  # Debounce: wait a moment after the last change, then apply once
  state = {'ready': False}
  timer = Timer(interval=0)

  def tick(**event_args):
    timer.interval = 0
    on_apply()
  timer.set_event_handler('tick', tick)

  def changed():
    if state['ready']:
      timer.interval = FILTER_DEBOUNCE_SECONDS

  for c in (toolbar, dropdown_panel, chips_row, timer):
    host.add_component(c)

  manager = FilterManager(dropdown_panel, on_change=changed,
                          defaults=defaults, project_privacy=project_privacy)
  manager.attach_toolbar(filters_btn, reset_btn, count_lbl,
                         _ChipRow(chips_flow, manager.remove), chips_row)
  state['ready'] = True
  return manager