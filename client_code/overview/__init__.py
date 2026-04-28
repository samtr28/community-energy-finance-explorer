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
    self.init_components(**properties)

    total_cost, project_num = anvil.server.call('get_summary_data')
    self.project_number.text = f"{project_num}"
    self.total_funding_number.text = f"${total_cost / 1e9:.1f}B"

    # load the province map
    self.province_map.figure = anvil.server.call('get_province_map')

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.overview_nav.role = 'selected'

  def owner_btn_click(self, **event_args):
    open_form('ownership_models')

  def outcome_btn_click(self, **event_args):
    open_form('outcomes_impacts')

  def cap_btn_click(self, **event_args):
    open_form('capital_explorer')

  def proj_btn_click(self, **event_args):
    open_form('projects_explorer')
