from ._anvil_designer import SubProjectRowTemplate
from anvil import *
import anvil.server
import m3.components as m3
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class SubProjectRow(SubProjectRowTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)
    self.sub_name_label.text = self.item.get("site_name", "")
    self.sub_type_label.text = self.item.get("project_type", "")
    cost = self.item.get("project_cost")
    if cost:
      self.sub_cost_label.text = f"${cost:,.0f}"
    else:
      self.sub_cost_label.text = "—"

    TYPE_ICONS = {
      'Biofuel/Biogas': 'mi:local_fire_department',
      'Solar': 'mi:solar_power',
      'Wind': 'mi:wind_power',
      'Hydro': 'mi:water_drop',
      'Biomass': 'mi:eco',
      'Energy storage': 'mi:battery_charging_full',
      'Geothermal': 'mi:thermostat',
      'Building efficiency upgrades': 'mi:apartment',
      'Heat pump': 'mi:heat_pump',
      'District energy': 'mi:device_hub',
    }

    icon_components = [self.type_icon_1, self.type_icon_2, self.type_icon_3, self.type_icon_4]

    types = self.item.get("project_type", [])
    if isinstance(types, str):
      types = [types]
  
    for i, icon_comp in enumerate(icon_components):
      if i < len(types):
        icon_comp.icon = TYPE_ICONS.get(types[i], 'mi:bolt')
        icon_comp.visible = True
      else:
        icon_comp.visible = False

  def sub_row_click(self, **event_args):
    """When a sub-project row is clicked, highlight on map"""
    form = get_open_form()
    form._handling_sub_click = True  # <-- add this

    sub_id = self.item.get("sub_id")
    point_idx = form._sub_id_to_point.get(sub_id)
    if point_idx is None:
      form._handling_sub_click = False
      return
    info = form._sub_parent_map.get(str(point_idx))
    if not info:
      form._handling_sub_click = False
      return
    form._select_sub_project(info["parent_pos"], info["sub_id"])