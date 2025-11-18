from ._anvil_designer import case_studiesTemplate
from anvil import *
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class case_studies(case_studiesTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    # Any code you write here will run before the form opens.
    def form_show(self, **event_args):
      """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.case_nav.role = 'selected'
    pass