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
from ..InfoPopupCE import InfoPopupCE
from ..filter_bar import build_filter_bar


class capital_explorer(capital_explorerTemplate):

  # ==================== INITIALISATION ====================

  def __init__(self, **properties):
    self.init_components(**properties)

    self._filters_loaded = False
    self._load_id = 0

    self.filters = build_filter_bar(
      self.filter_bar,
      on_apply=self.apply_filters,
      defaults={'project_scale': [
        "Micro (< $100K)", "Small ($100K-$1M)", "Medium ($1M-$5M)",
        "Large ($5M-$25M)", "Very Large ($25M-$100M)"
      ]},
    )

  def form_show(self, **event_args):
    """Load data once on first show, and highlight the nav link."""
    self.layout.reset_links()
    self.layout.capital_nav.role = 'selected'

    if not self._filters_loaded:
      self._filters_loaded = True
      self.apply_filters()

  # ==================== FILTERS ====================

  def _get_filter_kwargs(self):
    return self.filters.get_kwargs()

  def _get_active_filters(self):
    """Human-readable filter labels for export annotations."""
    return self.filters.get_active_labels()

  # ==================== CHART LOADING ====================

  def apply_filters(self):
    """
    Single server call that reloads all charts and indicators
    based on the current filter state.
    """
    self._load_id += 1
    load_id = self._load_id

    self.filters.refresh_ui()
    self.filters.show_loading()

    all_charts = anvil.server.call('get_all_capital_charts', **self._get_filter_kwargs())
    if load_id != self._load_id:
      return                       # a newer change started while this one loaded
    self.filters.show_count(all_charts)

    # ── Charts ──
    self.funding_time_plot.figure = all_charts['time_chart']
    self.capital_flow_plot.figure = all_charts['sankey']
    self.stacked_plot.figure      = all_charts['stacked_bar']
    self.box_plot.figure          = all_charts['box_plot']
    self.lollipop_chart.figure    = all_charts['bottleneck_chart']
    self.bubble_plot.figure       = all_charts['treemap']
    self.scale_pies_plot.figure   = all_charts['scale_pies']
    self.alt_financing_bar_plot.figure = all_charts['alt_financing_bar']


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
      'alt_financing_bar': self.alt_financing_bar_plot,
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

  def download_treemap_btn_click(self, **event_args):
    self._download_chart('treemap', button=self.download_treemap_btn)

  def download_pies_btn_click(self, **event_args):
    self._download_chart('scale_pies', button=self.download_pies_btn)


  def info_btn_click(self, **event_args):
    alert(
      content=InfoPopupCE(),
      title="How to use this page",
      large=True,                     # wider modal — good for lots of text
      buttons=[("Close", None)],      # single Close button
    )

