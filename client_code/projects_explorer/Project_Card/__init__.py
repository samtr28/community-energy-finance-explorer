from ._anvil_designer import Project_CardTemplate
from anvil import *
import plotly.graph_objects as go
import anvil.server
import m3.components as m3
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class Project_Card(Project_CardTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    # Any code you write here will run before the form opens.
    if self.item["data_source"]=="Survey response":
      self.data_source_pill.level="info"
    else: 
      self.data_source_pill.level="warning"
      
    self.ownership_plot.layout.barmode="stack"
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

    # 3) Apply your trace-wide updates (equivalent to fig.update_traces)
    for tr in self.ownership_plot.data:
      tr.texttemplate = "%{customdata[0]}: %{x:.0f}%"
      tr.textposition = "inside"
      tr["hovertemplate"] = "<b>%{customdata[0]}</b><br>Type: %{customdata[1]}<br>%: %{x:.1f}<extra></extra>"


  # 1) Set layout properties
# Adjust margin based on number of categories
    num_categories = len(set(tr.name for tr in self.capital_mix_plot.data))
    bottom_margin = 0 + (55 * (num_categories // 5))  # Add space for wrapping
    
    self.capital_mix_plot.layout.margin = dict(l=5, r=5, t=35, b=bottom_margin)
    
    self.capital_mix_plot.layout.barmode = "stack"
    #self.capital_mix_plot.layout.margin = dict(l=5, r=5, t=25, b=15)
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
    
    # 2) Hide the modebar
    self.capital_mix_plot.config = {"displayModeBar": False}
    
    # 3) Apply trace-wide updates
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
    # 4) Check for warnings and add annotations
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
  
  def project_card_click(self, **event_args):
    """This method is called when the component is clicked"""
    parent = self.parent  # the RepeatingPanel
    idx = parent.get_components().index(self)
    form = get_open_form()

    # Toggle: if clicking same card, unselect
    if hasattr(form, '_selected_idx') and form._selected_idx == idx:
      form._unselect_all()
    else:
      form._select_index(idx)
    
