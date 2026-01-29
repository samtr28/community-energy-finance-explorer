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

  def schedule_filter_update(self):
    """Schedule a filter update with debouncing - waits 1s after last change"""
    # Setting interval to non-zero starts/restarts the timer
    self.filter_timer.interval = 1

  def apply_filters(self):
    """Apply filters and update all charts with ONE server call"""
    print("CLIENT: ========== APPLY_FILTERS STARTED ==========")

    try:
      # Read current filter selections
      print("CLIENT: Reading filter selections...")

      provinces = self.provinces_dd.selected if hasattr(self, 'provinces_dd') else []
      proj_types = self.proj_types_dd.selected if hasattr(self, 'proj_types_dd') else []
      stages = self.stages_dd.selected if hasattr(self, 'stages_dd') else []
      indigenous_ownership = self.indig_owners_dd.selected if hasattr(self, 'indig_owners_dd') else []
      project_scale = self.project_scale_dd.selected if hasattr(self, 'project_scale_dd') else []

      print(f"CLIENT: provinces = {provinces}")
      print(f"CLIENT: proj_types = {proj_types}")
      print(f"CLIENT: stages = {stages}")
      print(f"CLIENT: indigenous_ownership = {indigenous_ownership}")
      print(f"CLIENT: project_scale = {project_scale}")

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

      print(f"CLIENT: Filters being applied: {kwargs}")

      # UPDATE CHIPS
      print("CLIENT: Building filter chips...")
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
      if hasattr(self, 'filter_chips_panel'):
        self.filter_chips_panel.items = chips
        print(f"CLIENT: Updated {len(chips)} filter chips")
      else:
        print("CLIENT: filter_chips_panel not found (skipping)")

      # SINGLE SERVER CALL - gets all charts at once
      print("CLIENT: About to call server...")
      all_charts = anvil.server.call('get_all_ownership_charts', **kwargs)
      print(f"CLIENT: Server call completed!")
      print(f"CLIENT: Received chart keys: {list(all_charts.keys()) if all_charts else 'None'}")

      # Update plots with the returned figures
      if hasattr(self, 'ownership_treemap'):
        print("CLIENT: Updating ownership_treemap...")
        self.ownership_treemap.figure = all_charts['ownership_treemap']
        print("CLIENT: ownership_treemap updated successfully")
      else:
        print("CLIENT ERROR: ownership_treemap component not found!")

      if hasattr(self, 'scale_pies_plot'):
        print("CLIENT: Updating scale_pies_plot...")
        self.scale_pies_plot.figure = all_charts['scale_pies']
        print("CLIENT: scale_pies_plot updated successfully")
      else:
        print("CLIENT ERROR: scale_pies_plot component not found!")

      print("CLIENT: ========== APPLY_FILTERS COMPLETED ==========")

    except Exception as e:
      print(f"CLIENT ERROR in apply_filters: {e}")

  def remove_filter(self, filter_type, value):
    """Remove a specific filter value and refresh"""
    print(f"CLIENT: remove_filter called - type: {filter_type}, value: {value}")

    try:
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
    except Exception as e:
      print(f"CLIENT ERROR in remove_filter: {e}")

  def provinces_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    print("CLIENT: provinces_dd changed")
    self.schedule_filter_update()

  def proj_types_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    print("CLIENT: proj_types_dd changed")
    self.schedule_filter_update()

  def stages_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    print("CLIENT: stages_dd changed")
    self.schedule_filter_update()

  def indig_owners_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    print("CLIENT: indig_owners_dd changed")
    self.schedule_filter_update()

  def project_scale_dd_change(self, **event_args):
    """This method is called when the selected values change"""
    print("CLIENT: project_scale_dd changed")
    self.schedule_filter_update()

  def form_show(self, **event_args):
    """This method is called when the form is shown on the page"""
    print("CLIENT: ========== FORM_SHOW CALLED ==========")
    try:
      print("CLIENT: Resetting navigation...")
      if hasattr(self, 'layout'):
        self.layout.reset_links()
        if hasattr(self.layout, 'ownership_nav'):
          self.layout.ownership_nav.role = 'selected'
          print("CLIENT: Navigation set")
        else:
          print("CLIENT WARNING: layout.ownership_nav not found")
      else:
        print("CLIENT WARNING: layout not found")

      # Load charts on initial page load
      print("CLIENT: Loading initial charts from form_show...")
      self.apply_filters()
    except Exception as e:
      print(f"CLIENT ERROR in form_show: {e}")

  def filter_timer_tick(self, **event_args):
    """This method is called when the timer fires"""
    # Stop the timer so it doesn't repeat
    self.filter_timer.interval = 0
    # Apply the filters
    self.apply_filters()