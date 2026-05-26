from ._anvil_designer import team_memberTemplate
from anvil import *
import anvil.server
import m3.components as m3
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class team_member(team_memberTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    super().__init__(**properties)
    self.link_faculty.visible = bool(self.item['faculty_page'])
    if self.item['faculty_page']:
      self.link_faculty.url = self.item['faculty_page']

    # LinkedIn link: same pattern
    self.link_linkedin.visible = bool(self.item['linkedin'])
    if self.item['linkedin']:
      self.link_linkedin.url = self.item['linkedin']
    # Any code you write here will run before the form opens.
