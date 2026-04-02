from ._anvil_designer import methodsTemplate
from anvil import *
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class methods(methodsTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    # Accordion sections
    self.sections = [
      (self.button_data, self.panel_data),
    ]

    for button, panel in self.sections:
      panel.visible = False
      button.icon = "mi:expand_circle_down"
      button.set_event_handler('click', self._make_handler(button, panel))


  def _make_handler(self, button, panel):
    def handler(**event_args):
      panel.visible = not panel.visible
      button.icon = (
        "mi:expand_circle_down" if panel.visible
        else "mi:expand_circle_up"
        )
    return handler

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.methods_nav.role = 'selected'
# Any code you write here will run before the form opens.

