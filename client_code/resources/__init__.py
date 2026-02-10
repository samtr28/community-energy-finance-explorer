from ._anvil_designer import resourcesTemplate
from anvil import *
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

class resources(resourcesTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)
    self.load_files()

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.resources_nav.role = 'selected'

  def load_files(self):
    """Fetch files from server and populate repeating panel"""
    files = anvil.server.call('get_pdf_files')
    self.repeating_panel_1.items = files