from ._anvil_designer import projects_explorerTemplate
from anvil import *
import m3.components as m3
import plotly.graph_objects as go
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.js


class projects_explorer(projects_explorerTemplate):
  def __init__(self, **properties):
#===========SET FORM PROPERTIES AND DATA BINDINGS
    self.init_components(**properties)
    self._hi_card = None  
#============ MAKE MAP 
    self.project_map.data=anvil.server.call('get_map_data')
    #map appearance
    self.project_map.layout.map = dict(center=dict(lat=57, lon=-97), zoom=2, style="carto-voyager")
    self.project_map.layout.template = "mykonos_light"
    self.project_map.layout.margin = dict(t=5, b=5, l=5, r=5)
#============ MAKE PROJECT CARDS 
    self.project_cards.items=anvil.server.call('get_project_card_data')

#============ FILTER FUNCTION
  def apply_filters(self):
    # read both current selections
    provinces  = self.provinces_dd.selected
    proj_types = self.proj_types_dd.selected
    stages = self.stages_dd.selected
    indigenous_ownership = self.indig_owners_dd.selected
    project_scale = self.project_scale_dd.selected
    
    # pass only the filters that are set
    kwargs = {}
    if provinces:  kwargs["provinces"]  = provinces
    if proj_types: kwargs["proj_types"] = proj_types
    if stages: kwargs["stages"] = stages
    if indigenous_ownership: kwargs["indigenous_ownership"] = indigenous_ownership
    if project_scale: kwargs["project_scale"] = project_scale
      
    # update both pieces using the same combined filters
    self.project_map.data = anvil.server.call("get_map_data", **kwargs)
    self.project_cards.items = anvil.server.call("get_project_card_data", **kwargs)

#============ DROPDOWNS THAT CALL THE FILTER FUNCTION
  def stages_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.apply_filters()
    pass

  def provinces_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.apply_filters()
    pass

  def proj_types_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.apply_filters()
    pass

  def indig_owners_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.apply_filters()
    pass

  def project_scale_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.apply_filters()
    pass



#============ CLICK EVENTS
  def _select_index(self, idx: int):
    """Highlight point idx on the map and the matching card."""
    # -- map: select just this point
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = [idx]
      self.project_map.figure = fig

    # -- card: scroll + highlight
    rows = self.project_cards.get_components()
    if 0 <= idx < len(rows):
      row = rows[idx]
      row.scroll_into_view()

      # clear previous highlight (efficient)
      if self._hi_card:
        self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()

      row.project_card.role = ((row.project_card.role or "") + " card-highlight").strip()
      self._hi_card = row.project_card

    # Track current selection
    self._selected_idx = idx

  def _unselect_all(self):
    """Clear selection from both map and cards."""
    # -- map: clear selection
    fig = self.project_map.figure
    if fig and fig.data:
      fig.data[0].selectedpoints = []
      self.project_map.figure = fig

    # -- card: remove highlight
    if self._hi_card:
      self._hi_card.role = (self._hi_card.role or "").replace("card-highlight", "").strip()
      self._hi_card = None

    # -- clear tracking
    self._selected_idx = None

  def project_map_click(self, points, **event_args):
    if not points:
      # Clicked empty area - unselect
      self._unselect_all()
      return

    idx = points[0]["point_number"]

    # Toggle: if clicking same point, unselect
    if hasattr(self, '_selected_idx') and self._selected_idx == idx:
      self._unselect_all()
    else:
      self._select_index(idx)

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.layout.projects_nav.role = 'selected'
    pass

  def load_more_button_click(self, **event_args):
    """This method is called when the component is clicked."""
    pass






    
