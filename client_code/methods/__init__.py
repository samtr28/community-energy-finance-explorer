from ._anvil_designer import methodsTemplate
from anvil import *
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from anvil.js import get_dom_node


class methods(methodsTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    # Accordion sections
    self.sections = [
      (self.button_data, self.panel_data),
      (self.button_survey, self.panel_survey),
      (self.button_interview, self.panel_interview),
      (self.button_projects, self.panel_projects),
      (self.button_comparable, self.panel_comparable),
      (self.button_validate, self.panel_validate),
      (self.button_update, self.panel_update), 
      (self.button_privacy, self.panel_privacy),
      (self.button_storage, self.panel_storage),
      (self.button_limitations, self.panel_limitations),
      (self.button_team, self.panel_team),
      (self.button_contribute, self.panel_contribute),
      (self.button_share, self.panel_share)
    ]
    for button, panel in self.sections:
      panel.visible = False
      button.icon = "mi:expand_circle_down"
      button.set_event_handler('click', self._make_handler(button, panel))
      dom = get_dom_node(button)
      btn = dom.querySelector('.anvil-m3-button')
      if btn:
        btn.style.borderRadius = "0"
        btn.style.border = "none"
        btn.style.borderBottom = "1px solid #005694"

  def _make_handler(self, button, panel):
    def handler(**event_args):
      panel.visible = not panel.visible
      button.icon = (
        "mi:expand_circle_up" if panel.visible
        else "mi:expand_circle_down"
      )
      dom = get_dom_node(button)
      btn = dom.querySelector('.anvil-m3-button')
      if btn:
        if panel.visible:
          btn.style.borderBottom = "none"
        else:
          btn.style.borderBottom = "1px solid #005493"
    return handler

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.methods_nav.role = 'selected'
# Any code you write here will run before the form opens.

