from ._anvil_designer import BaseTemplate
from anvil import *
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables

# Add these imports to your form (for iframe integration)
from anvil.js.window import jQuery
from anvil.js import get_dom_node

set_default_error_handling(print)

class Base(BaseTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    # Any code you write here will run before the form opens.

  def overview_nav_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form('overview')
    pass

  def capital_nav_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form('capital_explorer')
    pass

  def ownership_nav_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form('ownership_models')
    pass

  def outcomes_nav_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form('outcomes_impacts')
    pass

  def projects_nav_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form('projects_explorer')
    pass

  def case_nav_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form('case_studies')
    pass

  def methods_nav_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form('methods_context')
    pass

  def resources_nav_click(self, **event_args):
    """This method is called when the link is clicked"""
    open_form('resources')
    pass

  def reset_links(self, **event_args):
    self.overview_nav.role = ''
    self.capital_nav.role = ''
    self.ownership_nav.role = ''
    self.outcomes_nav.role = ''
    self.projects_nav.role = ''
    self.case_nav.role = ''
    self.resources_nav.role=''
    self.methods_nav.role=''
