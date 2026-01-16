from ._anvil_designer import FilterChipTemplate
from anvil import *
import anvil.server
import m3.components as m3
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class FilterChip(FilterChipTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)

    # Any code you write here will run before the form opens.

  def chip_label_close_click(self, **event_args):
    """This method is called when the close link is clicked"""
    filter_type, value = self.item["tag"]
    # Get the form from the top of the navigation tree
    form = get_open_form()

    form.remove_filter(filter_type, value)
