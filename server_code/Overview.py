import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import ast
import json
import urllib.request

from .Global_Server_Functions import get_data
from .Export_Utils import apply_display_template
from .config import (
COLOUR_MAPPING, gradient_palette, dunsparce_colors,
FONT_FAMILY, FONT_SIZE, FONT_COLOR,
)

DATA = get_data()


# ==================== PROVINCE MAP CONSTANTS ====================

ALL_PROVINCES = [
  "British Columbia", "Alberta", "Saskatchewan", "Manitoba", "Ontario",
  "Quebec", "New Brunswick", "Nova Scotia", "Prince Edward Island",
  "Newfoundland and Labrador", "Yukon Territory", "Northwest Territories", "Nunavut",
]

PROVINCE_CENTROIDS = {
  "British Columbia":          (54.0, -125.0),
  "Alberta":                   (54.5, -115.0),
  "Saskatchewan":              (54.0, -106.0),
  "Manitoba":                  (54.5, -98.0),
  "Ontario":                   (50.0, -86.0),
  "Quebec":                    (52.5, -72.0),
  "New Brunswick":             (46.5, -66.5),
  "Nova Scotia":               (45.0, -63.0),
  "Prince Edward Island":      (46.5, -63.0),
  "Newfoundland and Labrador": (53.5, -60.0),
  "Yukon Territory":           (63.0, -135.0),
  "Northwest Territories":     (65.0, -120.0),
  "Nunavut":                   (70.0, -90.0),
}

PROVINCE_FIX = {"Yukon": "Yukon Territory"}

# Load geojson once at module level
_GEOJSON_URL = "https://raw.githubusercontent.com/codeforgermany/click_that_hood/main/public/data/canada.geojson"
with urllib.request.urlopen(_GEOJSON_URL) as response:
  CANADA_GEO = json.load(response)


# ==================== CALLABLES ====================

@anvil.server.callable
def get_summary_data():
  total_cost = DATA['total_cost'].sum()
  project_num = DATA['num_projects_response'].sum()
  return total_cost, project_num


@anvil.server.callable
def get_province_map():
  """
    Choropleth: project count per province (log-scaled colour).
    Provinces with no data shown in light grey.
    Number labels on coloured provinces with white halo for legibility.
    Chart-specific properties only — generic styling handled by apply_display_template.
    """
  df = DATA.copy()
  df["province_geo"] = df["province"].replace(PROVINCE_FIX)

  province_counts = (
    df.groupby("province_geo")["num_projects_response"].sum()
      .reindex(ALL_PROVINCES, fill_value=0)
      .reset_index(name="projects")
  )
  province_counts.columns = ["province", "projects"]
  province_counts["projects_log"] = np.log1p(province_counts["projects"])
  province_counts["lat"] = province_counts["province"].map(lambda p: PROVINCE_CENTROIDS[p][0])
  province_counts["lon"] = province_counts["province"].map(lambda p: PROVINCE_CENTROIDS[p][1])

  has_data = province_counts[province_counts["projects"] > 0]
  no_data  = province_counts[province_counts["projects"] == 0]
  labeled  = province_counts[province_counts["projects"] > 0]

  fig = go.Figure()

  # Layer 1: grey "no data" provinces
  fig.add_trace(go.Choropleth(
    geojson=CANADA_GEO,
    locations=no_data["province"],
    z=[0] * len(no_data),
    featureidkey="properties.name",
    colorscale=[[0, "#e0e0e0"], [1, "#e0e0e0"]],
    showscale=False,
    marker_line_color="black",
    marker_line_width=0.5,
    hovertemplate="<b>%{location}</b><br>No projects<extra></extra>",
  ))

  # Layer 2: coloured "has data" provinces
  fig.add_trace(go.Choropleth(
    geojson=CANADA_GEO,
    locations=has_data["province"],
    z=has_data["projects_log"],
    customdata=has_data["projects"],
    featureidkey="properties.name",
    colorscale="Teal",
    showscale=False,
    marker_line_color="black",
    marker_line_width=0.5,
    hovertemplate="<b>%{location}</b><br>%{customdata} projects<extra></extra>",
  ))

  # Layer 3: white halo behind count labels
  halo_offset = 0.08
  for dlat, dlon in [(halo_offset, 0), (-halo_offset, 0), (0, halo_offset), (0, -halo_offset)]:
    fig.add_trace(go.Scattergeo(
      lon=labeled["lon"] + dlon,
      lat=labeled["lat"] + dlat,
      text=labeled["projects"].astype(int).astype(str),
      mode="text",
      textfont=dict(family=FONT_FAMILY, size=16, color="white", weight="bold"),
      hoverinfo="skip",
      showlegend=False,
    ))

    # Layer 4: main count labels
  fig.add_trace(go.Scattergeo(
    lon=labeled["lon"],
    lat=labeled["lat"],
    text=labeled["projects"].astype(int).astype(str),
    mode="text",
    textfont=dict(family=FONT_FAMILY, size=16, color=FONT_COLOR, weight="bold"),
    hoverinfo="skip",
    showlegend=False,
  ))

  fig.update_geos(
    fitbounds="geojson",
    visible=False,
    bgcolor="rgba(0,0,0,0)",       # transparent geo background
  )
  # Keep only essentials here (optional)
  fig.update_layout(
    title="Projects by province",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
  )

  # APPLY TEMPLATE FIRST
  fig = apply_display_template(fig)

  #  FORCE OVERRIDES AFTER TEMPLATE (this is the fix)
  fig.update_layout(
    margin=dict(l=0, r=0, t=0, b=0),
    title=dict(
      text="Projects by province",
      y=0.98,
      yanchor="top",
      pad=dict(t=0, b=0),
      automargin=False
    )
  )

  return fig


