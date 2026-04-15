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