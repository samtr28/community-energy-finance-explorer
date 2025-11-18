from ._anvil_designer import overviewTemplate
from anvil import *
import m3.components as m3
import plotly.graph_objects as go
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class overview(overviewTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    
    total_cost, row_count = anvil.server.call('get_summary_data')
    self.project_number.text = f"{row_count}"
    self.total_funding_number.text = f"${total_cost / 1e9:.1f}B"


    
    # Any code you write here will run before the form opens.
    def form_show(self, **event_args):
      """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.overview_nav.role = 'selected'
    pass
  

