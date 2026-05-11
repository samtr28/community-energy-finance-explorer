from ._anvil_designer import overviewTemplate
from anvil import *
import m3.components as m3
import plotly.graph_objects as go
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from ..chart_export import download_chart


class overview(overviewTemplate):

  # ==================== INITIALISATION ====================

  def __init__(self, **properties):
    self.init_components(**properties)
    self._data_loaded = False

  def form_show(self, **event_args):
    """Load data once on first show, and highlight the nav link."""
    self.layout.reset_links()
    self.layout.overview_nav.role = 'selected'

    if not self._data_loaded:
      self._data_loaded = True
      self.load_data()


  # ==================== DATA LOADING ====================

  def load_data(self):
    """Single server call to populate all summary stats and charts."""
    data = anvil.server.call('get_all_overview_data')

    # ── Summary stats ──
    summary = data['summary']
    self.project_number.text       = f"{summary['project_num']}"
    self.total_funding_number.text = f"${summary['total_cost'] / 1e9:.1f}B"

    # ── Charts ──
    self.province_map.figure       = data['province_map']
    self.mechanism_compare_plot.figure = data['mechanism_compare']


  # ==================== NAVIGATION ====================

  def owner_btn_click(self, **event_args):
    open_form('ownership_models')

  def outcome_btn_click(self, **event_args):
    open_form('outcomes_impacts')

  def cap_btn_click(self, **event_args):
    open_form('capital_explorer')

  def proj_btn_click(self, **event_args):
    open_form('projects_explorer')

  # ==================== CHART DOWNLOAD ====================

  def _get_plot_component(self, chart_key):
    """Maps a chart key string to the corresponding plot component."""
    return {
      'mechanism_compare': self.mechanism_compare_plot,
      'province_map':      self.province_map,
    }[chart_key]

  def _get_active_filters(self):
    """Overview has no filters — returns empty dict."""
    return {}

  def _download_chart(self, chart_key, button=None):
    """Capture and download any chart by key."""
    download_chart(
      plot_component=self._get_plot_component(chart_key),
      chart_key=chart_key,
      active_filters=self._get_active_filters(),
      server_callable='export_overview_chart',
      button=button,
    )

  def download_mechanism_btn_click(self, **event_args):
    self._download_chart('mechanism_compare', button=self.download_mechanism_btn)