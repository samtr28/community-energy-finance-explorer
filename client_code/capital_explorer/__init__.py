from ._anvil_designer import capital_explorerTemplate
from anvil import *
import plotly.graph_objects as go
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from .. import config
from ..chart_export import download_chart


class capital_explorer(capital_explorerTemplate):

  # ==================== INITIALISATION ====================

  def __init__(self, **properties):
    self.init_components(**properties)

    # Prevent filter events firing during setup
    self._initializing = True
    self._filters_loaded = False

    # Set default project scale selection
    self.project_scale_dd.selected = [
      "Micro (< $100K)", "Small ($100K-$1M)", "Medium ($1M-$5M)",
      "Large ($5M-$25M)", "Very Large ($25M-$100M)"
    ]

    self._initializing = False

  def form_show(self, **event_args):
    """Load data once on first show, and highlight the nav link."""
    self.layout.reset_links()
    self.layout.capital_nav.role = 'selected'

    if not self._filters_loaded:
      self._filters_loaded = True
      self.apply_filters()


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
      'provinces':          self.provinces_dd,
      'proj_types':         self.proj_types_dd,
      'stages':             self.stages_dd,
      'indigenous_ownership': self.indig_owners_dd,
      'project_scale':      self.project_scale_dd,
    }
    if filter_type in targets:
      current = list(targets[filter_type].selected)
      current.remove(value)
      targets[filter_type].selected = current
    self.schedule_filter_update()


  # ==================== FILTER HELPERS ====================

  def _get_filter_kwargs(self):
    """Returns only the filters that have values set, as server kwargs."""
    kwargs = {}
    if self.provinces_dd.selected:
      kwargs['provinces'] = self.provinces_dd.selected
    if self.proj_types_dd.selected:
      kwargs['proj_types'] = self.proj_types_dd.selected
    if self.stages_dd.selected:
      kwargs['stages'] = self.stages_dd.selected
    if self.indig_owners_dd.selected:
      kwargs['indigenous_ownership'] = self.indig_owners_dd.selected
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
      (self.provinces_dd.selected,       'provinces',           'Province'),
      (self.proj_types_dd.selected,      'proj_types',          'Project Type'),
      (self.stages_dd.selected,          'stages',              'Stage'),
      (self.indig_owners_dd.selected,    'indigenous_ownership','Indigenous'),
      (self.project_scale_dd.selected,   'project_scale',       'Scale'),
    ]
    for selected, filter_type, label in mappings:
      for value in (selected or []):
        chips.append({'text': f'{label}: {value}', 'tag': (filter_type, value)})
    return chips


  # ==================== CHART LOADING ====================

  def apply_filters(self):
    """
    Single server call that reloads all charts and indicators
    based on the current filter state.
    """
    # Update filter chips display
    self.filter_chips_panel.items = self._build_filter_chips()

    # Fetch all charts and indicators in one server call
    all_charts = anvil.server.call('get_all_capital_charts', **self._get_filter_kwargs())

    # ── Charts ──
    self.funding_time_plot.figure = all_charts['time_chart']
    self.capital_flow_plot.figure = all_charts['sankey']
    self.stacked_plot.figure      = all_charts['stacked_bar']
    self.box_plot.figure          = all_charts['box_plot']
    self.lollipop_chart.figure    = all_charts['bottleneck_chart']
    self.bubble_plot.figure       = all_charts['treemap']
    self.scale_pies_plot.figure   = all_charts['scale_pies']

    # ── Indicators ──
    indicators = all_charts['indicators']

    self.debt_interest.text  = indicators['debt']['interest']
    self.debt_repayment.text = indicators['debt']['repayment']
    self.debt_type.text      = indicators['debt']['type']
    self.debt_source.text    = indicators['debt']['source']

    # Uncomment when equity/grants/community/crowdfunding cards are added:
    # self.equity_type.text          = indicators['equity']['type']
    # self.equity_source.text        = indicators['equity']['source']
    # self.grants_type.text          = indicators['grants']['type']
    # self.grants_source.text        = indicators['grants']['source']
    # self.community_type.text       = indicators['community_finance']['type']
    # self.community_source.text     = indicators['community_finance']['source']
    # self.crowdfund_type.text       = indicators['crowdfunding']['type']
    # self.crowdfund_source.text     = indicators['crowdfunding']['source']


  # ==================== CHART DOWNLOAD ====================

  def _get_plot_component(self, chart_key):
    """Maps a chart key string to the corresponding plot component."""
    return {
      'box_plot':         self.box_plot,
      'time_chart':       self.funding_time_plot,
      'sankey':           self.capital_flow_plot,
      'stacked_bar':      self.stacked_plot,
      'bottleneck_chart': self.lollipop_chart,
      'treemap':          self.bubble_plot,
      'scale_pies':       self.scale_pies_plot,
    }[chart_key]

  def _download_chart(self, chart_key, button=None):
    """Capture and download any chart by key. Optionally pass the button for feedback."""
    download_chart(
      plot_component=self._get_plot_component(chart_key),
      chart_key=chart_key,
      active_filters=self._get_active_filters(),
      server_callable='export_capital_chart',
      button=button
    )

  # One handler per download button — wire each to its button in the designer
  def download_box_btn_click(self, **event_args):
    self._download_chart('box_plot', button=self.download_box_btn)

  def download_time_btn_click(self, **event_args):
    self._download_chart('time_chart', button=self.download_time_btn)

  def download_sankey_btn_click(self, **event_args):
    self._download_chart('sankey', button=self.download_sankey_btn)

  def download_stacked_btn_click(self, **event_args):
    self._download_chart('stacked_bar', button=self.download_stacked_btn)

  def download_bottleneck_btn_click(self, **event_args):
    self._download_chart('bottleneck_chart', button=self.download_bottleneck_btn)

  def download_treemap_btn_click(self, **event_args):
    self._download_chart('treemap', button=self.download_treemap_btn)

  def download_pies_btn_click(self, **event_args):
    self._download_chart('scale_pies', button=self.download_pies_btn)