from ._anvil_designer import ownership_modelsTemplate
from anvil import *
import plotly.graph_objects as go
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from .. import config
from ..chart_export import download_chart
from ..InfoPopupOM import InfoPopupOM


class ownership_models(ownership_modelsTemplate):

  # ==================== INITIALISATION ====================

  def __init__(self, **properties):
    self.init_components(**properties)

    # Prevent filter events firing during setup
    self._initializing = True
    self._filters_loaded = False

    self._setup_dropdown_formatters()  # before pre-selecting

    # Default project scale selection
    self.project_scale_dd.selected = [
      "Micro (< $100K)", "Small ($100K-$1M)", "Medium ($1M-$5M)",
      "Large ($5M-$25M)", "Very Large ($25M-$100M)"
    ]

    self._initializing = False

  def form_show(self, **event_args):
    """Load data once on first show, and highlight the nav link."""
    self.layout.reset_links()
    self.layout.ownership_nav.role = 'selected'

    if not self._filters_loaded:
      self._filters_loaded = True
      self.apply_filters()
  
    #=====================DROPDOWN SETUP=========================
  def _setup_dropdown_formatters(self):
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
    """Fires after the debounce delay — stops the timer and applies filters."""
    self.filter_timer.interval = 0
    self.apply_filters()

  # Filter change handlers — all route through the debounce timer
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
      (self.provinces_dd.selected,     'provinces',           'Province'),
      (self.proj_types_dd.selected,    'proj_types',          'Project Type'),
      (self.stages_dd.selected,        'stages',              'Stage'),
      (self.indig_owners_dd.selected,  'indigenous_ownership','Indigenous'),
      (self.project_scale_dd.selected, 'project_scale',       'Scale'),
    ]
    for selected, filter_type, label in mappings:
      for value in (selected or []):
        chips.append({'text': f'{label}: {value}', 'tag': (filter_type, value)})
    return chips


  # ==================== CHART LOADING ====================

  def apply_filters(self):
    """Single server call that reloads all charts based on current filter state."""
    self.filter_chips_panel.items = self._build_filter_chips()
    self.selected_panel.visible = len(self.filter_chips_panel.items) > 0

    all_charts = anvil.server.call('get_all_ownership_charts', **self._get_filter_kwargs())

    self.ownership_treemap.figure    = all_charts['ownership_treemap']
    self.scale_pies_plot.figure      = all_charts['scale_pies']
    self.indig_ownership_plot.figure = all_charts['indigenous_pie']
    self.lollipop_chart.figure       = all_charts['lollipop_chart']
    self.funnel_plot.figure          = all_charts['funnel_chart']


  # ==================== CHART DOWNLOAD ====================

  def _get_plot_component(self, chart_key):
    """Maps a chart key string to the corresponding plot component."""
    return {
      'ownership_treemap': self.ownership_treemap,
      'scale_pies':        self.scale_pies_plot,
      'indigenous_pie':    self.indig_ownership_plot,
      'lollipop_chart':    self.lollipop_chart,
      'funnel_chart':      self.funnel_plot,
    }[chart_key]

  def _download_chart(self, chart_key, button=None):
    """Capture and download any chart by key."""
    download_chart(
      plot_component=self._get_plot_component(chart_key),
      chart_key=chart_key,
      active_filters=self._get_active_filters(),
      server_callable='export_ownership_chart',
      button=button,
    )

  def info_btn_click(self, **event_args):
    alert(
      content=InfoPopupOM(),
      title="How to use this page",
      large=True,                     # wider modal — good for lots of text
      buttons=[("Close", None)],      # single Close button
    )

  # ── Wire one handler per download button. Add buttons in the designer first,
  #    then create the matching method here. Examples (uncomment when buttons exist):
  #
  # def download_treemap_btn_click(self, **event_args):
  #   self._download_chart('ownership_treemap', button=self.download_treemap_btn)
  #
  # def download_pies_btn_click(self, **event_args):
  #   self._download_chart('scale_pies', button=self.download_pies_btn)
  #
  # def download_indigenous_btn_click(self, **event_args):
  #   self._download_chart('indigenous_pie', button=self.download_indigenous_btn)
  #
  # def download_bottleneck_btn_click(self, **event_args):
  #   self._download_chart('lollipop_chart', button=self.download_bottleneck_btn)
  #
  # def download_funnel_btn_click(self, **event_args):
  #   self._download_chart('funnel_chart', button=self.download_funnel_btn)