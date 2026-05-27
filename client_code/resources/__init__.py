from ._anvil_designer import resourcesTemplate
from anvil import *
import plotly.graph_objects as go
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from .factsheet_data import factsheets
from ..chart_export import download_chart
from .external_resources_data import educational_resources, funding_resources

class resources(resourcesTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)
    self._data_loaded = False
    self.external_resources.items = educational_resources
    self.funding_resources.items = funding_resources


  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.resources_nav.role = 'selected'
    self.factsheets_panel.items = factsheets

    if not self._data_loaded:
      self._data_loaded = True
      self.load_data()

  def load_data(self):
    """Single server call to populate all Resources charts."""
    data = anvil.server.call('get_all_resources_data')
    self.mechanism_compare_plot.figure = data['mechanism_compare']

  def _get_plot_component(self, chart_key):
    return {
      'mechanism_compare': self.mechanism_compare_plot,
    }[chart_key]
  
    def _get_active_filters(self):
      return {}
  
  def _download_chart(self, chart_key, server_callable, button=None):
    download_chart(
      plot_component=self._get_plot_component(chart_key),
      chart_key=chart_key,
      active_filters=self._get_active_filters(),
      server_callable=server_callable,
      button=button,
    )
  
    def download_mechanism_btn_click(self, **event_args):
      self._download_chart(
        'mechanism_compare',
        server_callable='export_mechanism_chart',
        button=self.download_mechanism_btn,
      )