from ._anvil_designer import outcomes_impactsTemplate
from anvil import *
import plotly.graph_objects as go
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from .. import config


class outcomes_impacts(outcomes_impactsTemplate):

  # ==================== INITIALISATION ====================

  def __init__(self, **properties):
    self.init_components(**properties)

    self._initializing   = True
    self._filters_loaded = False

    self._setup_dropdown_formatters()

    self.project_scale_dd.selected = [
      "Micro (< $100K)", "Small ($100K-$1M)", "Medium ($1M-$5M)",
      "Large ($5M-$25M)", "Very Large ($25M-$100M)"
    ]

    self._initializing = False

  def form_show(self, **event_args):
    """Load data once on first show, and highlight the nav link."""
    self.layout.reset_links()
    self.layout.outcomes_nav.role = 'selected'

    if not self._filters_loaded:
      self._filters_loaded = True
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
    """Debounce filter changes — waits 1s after the last change before reloading."""
    if getattr(self, '_initializing', False):
      return
    self.filter_timer.interval = 1

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
    """Remove a single filter chip value and trigger a refresh."""
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

  def apply_filters(self):
    """Single server call that reloads all charts based on current filter state."""
    self.filter_chips_panel.items = self._build_filter_chips()

    all_charts = anvil.server.call('get_all_outcomes_charts', **self._get_filter_kwargs())

    self.indigenous_agreements_plot.figure  = all_charts['indigenous_agreements']
    self.jobs_plot.figure                   = all_charts['jobs_chart']
    self.ghg_methodology_plot.figure        = all_charts['ghg_methodology']
    self.ghg_timeline_plot.figure           = all_charts['ghg_timeline']
    self.key_objectives_plot.figure         = all_charts['key_objectives']
    self.key_objectives_lollipop_plot.figure = all_charts['key_objectives_lollipop']