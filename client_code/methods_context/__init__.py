from ._anvil_designer import methods_contextTemplate
from anvil import *
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class methods_context(methods_contextTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    
    def form_show(self, **event_args):
      """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.methods_nav.role = 'selected'
    pass
    # Any code you write here will run before the form opens.
