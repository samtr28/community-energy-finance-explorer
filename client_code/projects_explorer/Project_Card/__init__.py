from ._anvil_designer import Project_CardTemplate
from anvil import *
import plotly.graph_objects as go
import anvil.server
import m3.components as m3


class Project_Card(Project_CardTemplate):
  def __init__(self, **properties):
    self.init_components(**properties)

    # Set basic info
    if self.item["data_source"] == "Survey response":
      self.data_source_pill.level = "info"
    else:
      self.data_source_pill.level = "warning"

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

  def project_card_click(self, **event_args):
    """Handle card selection"""
    parent = self.parent
    card_idx = parent.get_components().index(self)
    form = get_open_form()

    # Calculate actual index in full dataset
    start_idx = (form._current_page - 1) * form._page_size
    actual_idx = start_idx + card_idx

    # Toggle selection
    if hasattr(form, '_selected_idx') and form._selected_idx == actual_idx:
      form._unselect_all()
    else:
      form._select_index(actual_idx)