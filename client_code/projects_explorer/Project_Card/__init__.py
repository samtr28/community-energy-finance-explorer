from ._anvil_designer import Project_CardTemplate
from anvil import *
import plotly.graph_objects as go
import anvil.server
import m3.components as m3


class Project_Card(Project_CardTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)
    # Show type icons
    # Set type icon
    # Set type icons (up to 4)
    TYPE_ICONS = {
      'Solar': 'mi:solar_power',
      'Wind': 'mi:wind_power',
      'Hydro': 'mi:water_drop',
      'Biomass': 'mi:local_fire_department',
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

        
    # Hide sub-project panel initially
    self.sub_projects_list.visible = False
    self.show_more_link.visible = False

    self._showing_all = False

    # Hide location if empty
    self.community.visible = bool(self.item.get("location_text"))

    # Set basic info
    if self.item["data_source"] == "Survey response":
      self.data_source_pill.level = "info"
    else:
      self.data_source_pill.level = "warning"

    # Show sub-project count for portfolios
    subs = self.item.get("sub_projects", [])
    if subs and len(subs) > 0:
      self.sub_projects_label.text = f"Portfolio · {len(subs)} sub-projects ▾"
      self.sub_projects_label.visible = True
    else:
      self.sub_projects_label.visible = False

    # Setup ownership plot immediately
    self.ownership_plot.data = self.item["ownership_traces"]
    self.ownership_plot.layout.barmode = "stack"
    self.ownership_plot.layout.margin = dict(l=5, r=5, t=30, b=5)
    self.ownership_plot.layout.showlegend = False
    self.ownership_plot.layout.xaxis = dict(ticksuffix="%", visible=False, range=[0, 100])
    self.ownership_plot.layout.yaxis = dict(visible=False)
    self.ownership_plot.config = {"displayModeBar": False}
    self.ownership_plot.layout.title = {
      'text': 'Ownership Distribution',
      'font': {'family': 'Noto Sans', 'size': 16, 'color': 'black'},
      'x': 0.01,
      'xanchor': 'left'
    }

    for tr in self.ownership_plot.data:
      tr.texttemplate = "%{customdata[0]}: %{x:.0f}%"
      tr.textposition = "inside"
      tr["hovertemplate"] = "<b>%{customdata[0]}</b><br>Type: %{customdata[1]}<br>%: %{x:.1f}<extra></extra>"

    # Setup capital mix plot immediately
    self.capital_mix_plot.data = self.item["capital_mix_traces"]

    num_categories = len(set(tr.name for tr in self.capital_mix_plot.data))
    bottom_margin = 0 + (55 * (num_categories // 5))

    self.capital_mix_plot.layout.margin = dict(l=5, r=5, t=35, b=bottom_margin)
    self.capital_mix_plot.layout.barmode = "stack"
    self.capital_mix_plot.layout.legend = dict(
      orientation="h",
      yanchor="bottom",
      y=-1,
      xanchor="right",
      x=1,
      bgcolor="rgba(0,0,0,0)",
      font=dict(size=10)
    )
    self.capital_mix_plot.layout.xaxis = dict(ticksuffix="%", visible=False, range=[0, 100])
    self.capital_mix_plot.layout.yaxis = dict(visible=False)
    self.capital_mix_plot.layout.title = {
      'text': 'Capital Mix',
      'font': {'family': 'Noto Sans', 'size': 16, 'color': 'black'},
      'x': 0.01,
      'xanchor': 'left'
    }
    self.capital_mix_plot.config = {"displayModeBar": False}

    for tr in self.capital_mix_plot.data:
      tr.texttemplate = "%{x:.0f}%"
      tr.textposition = "inside"
      tr.textfont = dict(size=12)
      tr["hovertemplate"] = (
        "<b>%{customdata[0]}</b><br>"
        "Type: %{customdata[1]}<br>"
        "Name: %{customdata[2]}<br>"
        "Percent: %{customdata[3]:.1f}%<br>"
        "Amount: $%{customdata[4]:,.0f}"
        "<extra></extra>"
      )

    # Check for warnings
    has_unknown = any(tr.name == "Other" and any("Unknown" in str(cd[2]) for cd in tr.customdata)
                      for tr in self.capital_mix_plot.data)

    total_percent = sum(tr.x[0] for tr in self.capital_mix_plot.data if tr.x)

    if has_unknown:
      self.capital_mix_plot.layout.annotations = [
        dict(
          text="⚠️ Unknown capital added to reach 100%",
          xref="paper", yref="paper",
          x=0.5, y=1.2,
          showarrow=False,
          font=dict(size=12, color="orange"),
          xanchor="center"
        )
      ]
    elif total_percent > 105:
      self.capital_mix_plot.layout.annotations = [
        dict(
          text=f"⚠️ Over-accounted (total: {total_percent:.0f}%)",
          xref="paper", yref="paper",
          x=0.5, y=1.2,
          showarrow=False,
          font=dict(size=12, color="red"),
          xanchor="center"
        )
      ]

    # Show/hide portfolio pill
    self.portfolio_pill.visible = bool(self.item.get("portfolio_text"))

    
  def project_card_click(self, **event_args):
    """Handle card selection"""
    form = get_open_form()

    # Skip if this was triggered by a sub-project click bubbling up
    if getattr(form, '_handling_sub_click', False):
      form._handling_sub_click = False
      return

    parent = self.parent
    card_idx = parent.get_components().index(self)

    start_idx = (form._current_page - 1) * form._page_size
    actual_idx = start_idx + card_idx

    if hasattr(form, '_selected_idx') and form._selected_idx == actual_idx:
      form._unselect_all()
    else:
      form._select_index(actual_idx)

  def toggle_sub_list(self, **event_args):
    """Toggle the sub-project list visibility"""
    self.sub_projects_list.visible = not self.sub_projects_list.visible
  
    if self.sub_projects_list.visible:
      subs = self.item.get("sub_projects", [])
      self.sub_projects_list.items = subs[:5]
      self._showing_all = len(subs) <= 5
  
      if not self._showing_all:
        self.sub_projects_label.text = f"Portfolio · showing 5 of {len(subs)} ▾"
        self.show_more_link.text = f"Show all {len(subs)} sub-projects ▾"
        self.show_more_link.visible = True
      else:
        self.sub_projects_label.text = f"Portfolio · {len(subs)} sub-projects ▴"
        self.show_more_link.text = "Collapse ▴"
        self.show_more_link.visible = True
    else:
      subs = self.item.get("sub_projects", [])
      self.sub_projects_label.text = f"Portfolio · {len(subs)} sub-projects ▾"
      self.sub_projects_list.items = []
      self.show_more_link.visible = False

  def highlight_sub_row(self, sub_id):
    """Highlight the selected sub-project row"""
    for row in self.sub_projects_list.get_components():
      if row.item.get("sub_id") == sub_id:
        row.sub_project_card.role = "sub-card-highlight"
      else:
        row.sub_project_card.role = ""

  def clear_sub_highlight(self):
    """Clear all sub-project row highlights"""
    for row in self.sub_projects_list.get_components():
      row.sub_project_card.role = ""

  def show_more_click(self, **event_args):
    """Show all sub-projects or collapse the list"""
    if self._showing_all:
      # Collapse the list
      self.toggle_sub_list()
    else:
      # Show all
      subs = self.item.get("sub_projects", [])
      self.sub_projects_list.items = subs
      self._showing_all = True
      self.show_more_link.text = "Collapse ▴"
      self.sub_projects_label.text = f"Portfolio · {len(subs)} sub-projects ▴"