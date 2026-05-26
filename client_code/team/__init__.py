from ._anvil_designer import teamTemplate
from anvil import *
import anvil.server
import m3.components as m3
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from .team_data import core_team, advisory_team


class team(teamTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.team_nav.role = 'selected'
    # Any code you write here will run before the form opens.
    self.core_team_panel.items = core_team
    self.advisory_panel.items = advisory_team
