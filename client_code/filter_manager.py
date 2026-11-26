import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from anvil_extras.MultiSelectDropDown import MultiSelectDropDown
from .filter_config import FILTERS, OWNER_CATEGORY_ORDER


class FilterManager:
  """Builds the filter dropdowns into a FlowPanel and handles kwargs, chips and labels."""

  def __init__(self, panel, on_change, defaults=None, specs=FILTERS, project_privacy=False):
    self._specs = list(specs)
    self._on_change = on_change
    self._dds = {}

    # Values found in the data, for dropdowns marked items_from: 'data'
    self._present = {}
    if any(s.get('items_from') == 'data' for s in self._specs):
      self._present = anvil.server.call('get_filter_options', project_privacy)

    # Owner categories and subtypes, for dropdowns marked items_from: 'owner_options'
    self._owner_options = {}
    if any(s.get('items_from') == 'owner_options' for s in self._specs):
      self._owner_options = anvil.server.call('get_owner_type_options')

    for spec in self._specs:
      dd = MultiSelectDropDown(
        placeholder=spec['label'],
        multiple=True,
        items=self._items_for(spec),
      )
      dd.format_selected_text = self._make_formatter(spec['label'])
      dd.set_event_handler('change', self._make_handler(spec['key']))
      panel.add_component(dd)
      self._dds[spec['key']] = dd

    # Pre-select defaults (skipping any value that is not in the dropdown)
    for key, selected in (defaults or {}).items():
      if key in self._dds:
        available = set(self._dds[key].items or [])
        self._dds[key].selected = [v for v in selected if v in available]

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

  def get_chips(self):
    chips = []
    for spec in self._specs:
      for value in (self._dds[spec['key']].selected or []):
        chips.append({'text': f"{spec['chip']}: {value}", 'tag': (spec['key'], value)})
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