from ._anvil_designer import ownership_modelsTemplate
from anvil import *
import plotly.graph_objects as go
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from .. import config

class ownership_models(ownership_modelsTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    self.project_scale_dd.selected = ["Micro (< $100K)", "Small ($100K-$1M)", "Medium ($1M-$5M)", "Large ($5M-$25M)", "Very Large ($25M-$100M)"]
    #self.filter_timer.interval = 1
    #self.apply_filters() 

  def schedule_filter_update(self):
    """Schedule a filter update with debouncing - waits 1s after last change"""
    # Setting interval to non-zero starts/restarts the timer
    self.filter_timer.interval=1

  def apply_filters(self):
    """Apply filters and update all charts with ONE server call"""
    # Read current filter selections
    provinces = self.provinces_dd.selected
    proj_types = self.proj_types_dd.selected
    stages = self.stages_dd.selected
    indigenous_ownership = self.indig_owners_dd.selected
    project_scale = self.project_scale_dd.selected
  
    # Build kwargs with only set filters
    kwargs = {}
    if provinces:
      kwargs["provinces"] = provinces
    if proj_types:
      kwargs["proj_types"] = proj_types
    if stages:
      kwargs["stages"] = stages
    if indigenous_ownership:
      kwargs["indigenous_ownership"] = indigenous_ownership
    if project_scale:
      kwargs["project_scale"] = project_scale
  
      # UPDATE CHIPS - Build chip data from selections
    chips = []
    
    if provinces:
      for p in provinces:
        chips.append({'text': f'Province: {p}', 'tag': ('provinces', p)})
    if proj_types:
      for pt in proj_types:
        chips.append({'text': f'Project Type: {pt}', 'tag': ('proj_types', pt)})
    if stages:
      for s in stages:
        chips.append({'text': f'Stage: {s}', 'tag': ('stages', s)})
    if indigenous_ownership:
      for io in indigenous_ownership:
        chips.append({'text': f'Indigenous: {io}', 'tag': ('indigenous_ownership', io)})
    if project_scale:
      for ps in project_scale:
        chips.append({'text': f'Scale: {ps}', 'tag': ('project_scale', ps)})
  
      # Update the repeating panel
    self.filter_chips_panel.items = chips
  
    # SINGLE SERVER CALL - gets all charts at once
    print("Fetching all charts...")
    all_charts = anvil.server.call('get_all_ownership_charts', **kwargs)
    print("Charts received, updating UI...")
  
    self.ownership_treemap.figure = all_charts['ownership_treemap']
    self.scale_pies_plot.figure =all_charts['scale_pies']
    self.indig_ownership_plot.figure = all_charts['indigenous_pie']
    self.lollipop_chart.figure = all_charts['lollipop_chart']
    self.funnel_plot.figure = all_charts['funnel_chart']

  def remove_filter(self, filter_type, value):
    """Remove a specific filter value and refresh"""
    # Remove the value from the appropriate dropdown
    if filter_type == 'provinces':
      current = list(self.provinces_dd.selected)
      current.remove(value)
      self.provinces_dd.selected = current
    elif filter_type == 'proj_types':
      current = list(self.proj_types_dd.selected)
      current.remove(value)
      self.proj_types_dd.selected = current
    elif filter_type == 'stages':
      current = list(self.stages_dd.selected)
      current.remove(value)
      self.stages_dd.selected = current
    elif filter_type == 'indigenous_ownership':
      current = list(self.indig_owners_dd.selected)
      current.remove(value)
      self.indig_owners_dd.selected = current
    elif filter_type == 'project_scale':
      current = list(self.project_scale_dd.selected)
      current.remove(value)
      self.project_scale_dd.selected = current

      # Schedule update with debouncing
    self.schedule_filter_update()

  def provinces_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.schedule_filter_update()

  def proj_types_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.schedule_filter_update()

  def stages_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.schedule_filter_update()

  def indig_owners_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.schedule_filter_update()

  def project_scale_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    self.schedule_filter_update()

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    self.layout.reset_links()
    self.ownership_nav.role = 'selected'
    self.apply_filters()
    
  def filter_timer_tick(self, **event_args):
    """This method is called when the timer fires"""
    # Stop the timer so it doesn't repeat
    self.filter_timer.interval = 0
    # Apply the filters
    self.apply_filters()
