from ._anvil_designer import outcomes_impactsTemplate
from anvil import *
import plotly.graph_objects as go
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from .. import config
from ..chart_export import download_chart
# Optional info popup — uncomment once you've created an info form for this page.
from ..InfoPopupOI import InfoPopupOI
from ..filter_bar import build_filter_bar


class outcomes_impacts(outcomes_impactsTemplate):

  # ==================== INITIALISATION ====================

  def __init__(self, **properties):
    self.init_components(**properties)

    self._filters_loaded = False
    self._load_id = 0

    # No default selections on this page
    self.filters = build_filter_bar(
      self.filter_bar,
      on_apply=self.apply_filters,
    )

  def form_show(self, **event_args):
    """Load data once on first show, and highlight the nav link."""
    self.layout.reset_links()
    self.layout.outcomes_nav.role = 'selected'

    if not self._filters_loaded:
      self._filters_loaded = True
      self.apply_filters()

  # ==================== FILTER HELPERS ====================

  def _get_filter_kwargs(self):
    return self.filters.get_kwargs()

  def _get_active_filters(self):
    """Human-readable filter labels for export annotations."""
    return self.filters.get_active_labels()

  # ==================== CHART LOADING ====================

  def apply_filters(self):
    """Single server call that reloads all charts based on the current filter state."""
    self._load_id += 1
    load_id = self._load_id

    self.filters.refresh_ui()
    self.filters.show_loading()

    all_charts = anvil.server.call('get_all_outcomes_charts', **self._get_filter_kwargs())
    if load_id != self._load_id:
      return                       # a newer change started while this one loaded
    self.filters.show_count(all_charts)

    # -- Charts --
    self.indigenous_agreements_plot.figure = all_charts['indigenous_agreements']
    self.jobs_plot.figure                  = all_charts['jobs_chart']
    self.ghg_methodology_plot.figure       = all_charts['ghg_methodology']
    self.ghg_timeline_plot.figure          = all_charts['ghg_timeline']
    self.key_objectives_plot.figure        = all_charts['key_objectives']
    self.op_expenses_plot.figure           = all_charts['op_expenses']
    self.return_expectations_plot.figure   = all_charts['return_expectations']
    self.end_use_plot.figure               = all_charts['end_use_composition']

  # ==================== CHART DOWNLOAD ====================

  def _get_plot_component(self, chart_key):
    """Maps a chart key string to the corresponding plot component."""
    return {
      'indigenous_agreements': self.indigenous_agreements_plot,
      'jobs_chart':            self.jobs_plot,
      'ghg_methodology':       self.ghg_methodology_plot,
      'ghg_timeline':          self.ghg_timeline_plot,
      'key_objectives':        self.key_objectives_plot,
      'return_expectations':   self.return_expectations_plot,
      'end_use_composition':   self.end_use_plot
    }[chart_key]

  def _download_chart(self, chart_key, button=None):
    """Capture and download any chart by key. Optionally pass the button for feedback."""
    download_chart(
      plot_component=self._get_plot_component(chart_key),
      chart_key=chart_key,
      active_filters=self._get_active_filters(),
      server_callable='export_outcomes_chart',
      button=button
    )

  # One handler per download button -- wire each to its button in the designer
  def download_indigenous_btn_click(self, **event_args):
    self._download_chart('indigenous_agreements', button=self.download_indigenous_btn)

  def download_jobs_btn_click(self, **event_args):
    self._download_chart('jobs_chart', button=self.download_jobs_btn)

  def download_ghg_methodology_btn_click(self, **event_args):
    self._download_chart('ghg_methodology', button=self.download_ghg_methodology_btn)

  def download_ghg_timeline_btn_click(self, **event_args):
    self._download_chart('ghg_timeline', button=self.download_ghg_timeline_btn)

  def download_key_objectives_btn_click(self, **event_args):
    self._download_chart('key_objectives', button=self.download_key_objectives_btn)

  # ==================== INFO POPUP ====================
  # Optional -- mirrors capital_explorer's info button.
  # Create an info form (e.g. InfoPopupOI), uncomment its import at the top,
  # add an info button in the designer, and wire it to this handler.
  #
  def info_btn_click(self, **event_args):
     alert(
       content=InfoPopupOI(),
       title="How to use this page",
       large=True,
       buttons=[("Close", None)],
     )
