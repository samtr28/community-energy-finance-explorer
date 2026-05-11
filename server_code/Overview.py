"""
Overview.py — Server module for the Overview page
==================================================
Structure:
  1. Imports
  2. Constants & static data       — provinces, geojson
  3. Utility functions             — phrase normalisation
  4. Main callable                 — get_all_overview_data()
  5. Chart creation functions      — one per chart

Display template is applied centrally in get_all_overview_data() via
apply_display_template() from Export_Utils. The province map handles its
own template + post-template override internally (see comment in
create_province_map_internal).
"""

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
import json
import urllib.request

from .Global_Server_Functions import get_data
from .Export_Utils import apply_display_template
from .config import (
COLOUR_MAPPING, gradient_palette, dunsparce_colors,
FONT_FAMILY, FONT_SIZE, FONT_COLOR,
)


# ==================== CONSTANTS ====================

ALL_PROVINCES = [
  "British Columbia", "Alberta", "Saskatchewan", "Manitoba", "Ontario",
  "Quebec", "New Brunswick", "Nova Scotia", "Prince Edward Island",
  "Newfoundland and Labrador", "Yukon Territory", "Northwest Territories", "Nunavut",
]

PROVINCE_CENTROIDS = {
  "British Columbia":          (54.0, -125.0),
  "Alberta":                   (54.5, -115.0),
  "Saskatchewan":              (54.0, -106.0),
  "Manitoba":                  (54.5,  -98.0),
  "Ontario":                   (50.0,  -86.0),
  "Quebec":                    (52.5,  -72.0),
  "New Brunswick":             (46.5,  -66.5),
  "Nova Scotia":               (45.0,  -63.0),
  "Prince Edward Island":      (46.5,  -63.0),
  "Newfoundland and Labrador": (53.5,  -60.0),
  "Yukon Territory":           (63.0, -135.0),
  "Northwest Territories":     (65.0, -120.0),
  "Nunavut":                   (70.0,  -90.0),
}

PROVINCE_FIX = {"Yukon": "Yukon Territory"}

# Load geojson once at module level — it never changes
_GEOJSON_URL = "https://raw.githubusercontent.com/codeforgermany/click_that_hood/main/public/data/canada.geojson"
with urllib.request.urlopen(_GEOJSON_URL) as response:
  CANADA_GEO = json.load(response)


# ==================== UTILITY FUNCTIONS ====================

def normalize_phrase(s):
  """
  Standardise a phrase for alias matching:
    - strip whitespace
    - lowercase
    - collapse internal whitespace to single spaces
    - replace en-dashes, em-dashes, and minus signs with regular hyphens

  Without dash normalisation, survey responses with curly/typographic dashes
  (e.g. 'Public–Private Partnerships') silently miss the alias map.
  """
  if not s:
    return ''
  s = (s.replace('\u2013', '-')   # en-dash
    .replace('\u2014', '-')   # em-dash
    .replace('\u2212', '-'))  # minus sign
  return ' '.join(s.strip().lower().split())


# ==================== MAIN CALLABLE ====================

@anvil.server.callable
def get_all_overview_data():
  """
  Single server call returning summary stats and all overview charts.
  Data is loaded once and shared across all chart builders.
  """
  df = get_data()

  return {
    'summary': {
      'total_cost':  df['total_cost'].sum(),
      'project_num': df['num_projects_response'].sum(),
    },
    # Province map applies its own template internally because it requires
    # post-template overrides for title positioning and margins.
    'province_map':      create_province_map_internal(df),
    'mechanism_compare': apply_display_template(create_mechanism_compare_internal(df)),
  }


# ==================== CHART CREATION ====================

def create_province_map_internal(df):
  """
  Choropleth: project count per province (log-scaled colour).
  Provinces with no data shown in light grey.
  Number labels on coloured provinces with white halo for legibility.

  Applies apply_display_template internally and then force-overrides title
  positioning and margins. This is needed because the template's title
  settings interfere with the geo layout.
  """
  df = df.copy()
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

  has_data = province_counts[province_counts["projects"] >  0]
  no_data  = province_counts[province_counts["projects"] == 0]
  labeled  = has_data

  fig = go.Figure()

  # Layer 1 — grey "no data" provinces
  fig.add_trace(go.Choropleth(
    geojson=CANADA_GEO,
    locations=no_data["province"],
    z=[0] * len(no_data),
    featureidkey="properties.name",
    colorscale=[[0, "#e0e0e0"], [1, "#e0e0e0"]],
    showscale=False,
    marker_line_color="black", marker_line_width=0.5,
    hovertemplate="<b>%{location}</b><br>No projects<extra></extra>",
  ))

  # Layer 2 — coloured "has data" provinces
  fig.add_trace(go.Choropleth(
    geojson=CANADA_GEO,
    locations=has_data["province"],
    z=has_data["projects_log"],
    customdata=has_data["projects"],
    featureidkey="properties.name",
    colorscale="Teal",
    showscale=False,
    marker_line_color="black", marker_line_width=0.5,
    hovertemplate="<b>%{location}</b><br>%{customdata} projects<extra></extra>",
  ))

  # Layer 3 — white halo behind count labels
  halo_offset = 0.08
  for dlat, dlon in [(halo_offset, 0), (-halo_offset, 0), (0, halo_offset), (0, -halo_offset)]:
    fig.add_trace(go.Scattergeo(
      lon=labeled["lon"] + dlon,
      lat=labeled["lat"] + dlat,
      text=labeled["projects"].astype(int).astype(str),
      mode="text",
      textfont=dict(family=FONT_FAMILY, size=16, color="white", weight="bold"),
      hoverinfo="skip", showlegend=False,
    ))

  # Layer 4 — main count labels
  fig.add_trace(go.Scattergeo(
    lon=labeled["lon"], lat=labeled["lat"],
    text=labeled["projects"].astype(int).astype(str),
    mode="text",
    textfont=dict(family=FONT_FAMILY, size=16, color=FONT_COLOR, weight="bold"),
    hoverinfo="skip", showlegend=False,
  ))

  fig.update_geos(
    fitbounds="geojson",
    visible=False,
    bgcolor="rgba(0,0,0,0)",
  )

  # Apply the template, then force-override title and margins
  fig = apply_display_template(fig)
  fig.update_layout(
    margin=dict(l=0, r=0, t=0, b=0),
    title=dict(
      text="Projects by province",
      y=0.98, yanchor="top",
      pad=dict(t=0, b=0),
      automargin=False,
    ),
  )
  return fig


def create_mechanism_compare_internal(df):
  """
  Grouped horizontal bar chart comparing financing mechanisms currently used
  vs. those respondents want to learn more about. Sorted by gap
  (want_to_learn - used). Annotations mark phrases that weren't asked about
  in one of the two questions.

  Chart-specific: horizontal grouped bars, dynamic height based on phrase count,
  legend on top, italic 'No data collected' annotations on missing bars.
  """
  # ── Alias map: collapses different wordings of the same concept ──
  # Keys MUST be in normalized form (lowercase, hyphens, single-spaced)
  ALIASES = {
    # grants
    'grants & non-repayable contributions': 'grants & non-repayable funding',
    'grants and non-repayable funding':     'grants & non-repayable funding',
    # tax credits
    'tax credits/accelerated depreciation':    'tax credits / accelerated depreciation',
    'tax credits or accelerated depreciation': 'tax credits / accelerated depreciation',
    # community finance
    'community-finance models':      'community investment vehicles',
    'community investment vehicles': 'community investment vehicles',
    # equity
    'equity investments': 'equity financing',
    'equity financing':   'equity financing',
    # internal capital
    'internal/owner-contributed capital': 'internal / owner-contributed capital',
    # leasing / PPAs
    'leasing/ppa models':                   'leasing / PPA models',
    'leasing/third-party ownership models': 'leasing / PPA models',
    # loan guarantees
    'loan guarantees or credit enhancements': 'loan guarantees / credit enhancements',
    'loan guarantees/credit enhancements':    'loan guarantees / credit enhancements',
    # public-private partnerships  ── extra variants added to catch P3 wording mismatches
    'public-private partnership (p3)':   'public-private partnerships',
    'public-private partnerships (p3)':  'public-private partnerships',
    'public-private partnerships (p3s)': 'public-private partnerships',
    'public-private partnership':        'public-private partnerships',
    'public-private partnerships':       'public-private partnerships',
    # crowdfunding
    'crowdfunded campaigns':  'crowdfunding campaigns',
    'crowdfunding campaigns': 'crowdfunding campaigns',
  }
  SKIP = {'other', 'not sure', 'other sources of capital and financial arrangements'}

  if (df.empty
      or 'all_financing_mechanisms' not in df.columns
      or 'ux_learn' not in df.columns):
    fig = go.Figure()
    fig.update_layout(title=dict(text='No financing mechanism data available'))
    return fig

  def count_phrases(series):
    freqs = {}
    for cell in series.dropna():
      for phrase in (cell or []):
        if not phrase:
          continue
        key = normalize_phrase(phrase)
        key = ALIASES.get(key, key)
        if key in SKIP:
          continue
        freqs[key] = freqs.get(key, 0) + 1
    return freqs

  used_freqs  = count_phrases(df['all_financing_mechanisms'])
  learn_freqs = count_phrases(df['ux_learn'])

  if not used_freqs and not learn_freqs:
    fig = go.Figure()
    fig.update_layout(title=dict(text='No financing mechanism data available'))
    return fig

  asked_used  = set(used_freqs)
  asked_learn = set(learn_freqs)
  all_phrases = asked_used | asked_learn

  compare = pd.DataFrame({
    'phrase':        list(all_phrases),
    'used':          [used_freqs.get(p, 0)  for p in all_phrases],
    'want_to_learn': [learn_freqs.get(p, 0) for p in all_phrases],
  })
  compare['gap']         = compare['want_to_learn'] - compare['used']
  compare['used_asked']  = compare['phrase'].isin(asked_used)
  compare['learn_asked'] = compare['phrase'].isin(asked_learn)
  plot_data = compare.sort_values('gap').reset_index(drop=True)

  # ── Capitalise phrases for display ──
  display_labels = [p[:1].upper() + p[1:] for p in plot_data['phrase']]

  fig = go.Figure()
  fig.add_trace(go.Bar(
    y=display_labels,
    x=plot_data['used'],
    name='Currently used',
    orientation='h',
    marker_color=dunsparce_colors[1],
    hovertemplate='<b>%{y}</b><br>Currently used: %{x}<extra></extra>',
  ))
  fig.add_trace(go.Bar(
    y=display_labels,
    x=plot_data['want_to_learn'],
    name='Want to learn about',
    orientation='h',
    marker_color=dunsparce_colors[3],
    hovertemplate='<b>%{y}</b><br>Want to learn: %{x}<extra></extra>',
  ))

  # ── 'No data collected' annotations for missing bars ──
  # <i>...</i> instead of font.style — style is not a valid plotly font property
  annotations = []
  for label, (_, row) in zip(display_labels, plot_data.iterrows()):
    if not row['used_asked']:
      annotations.append(dict(
        x=0, y=label,
        text='<i>No data collected (currently used)</i>',
        showarrow=False,
        font=dict(family=FONT_FAMILY, size=10, color='gray'),
        xanchor='left', yanchor='top', yshift=-1,
      ))
    if not row['learn_asked']:
      annotations.append(dict(
        x=0, y=label,
        text='<i>No data collected (want to learn)</i>',
        showarrow=False,
        font=dict(family=FONT_FAMILY, size=10, color='gray'),
        xanchor='left', yanchor='bottom', yshift=1,
      ))

  fig.update_layout(
    barmode='group',
    xaxis_title='Number of responses',
    yaxis_title='',
    height=max(500, 40 * len(plot_data)),
    annotations=annotations,
    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    margin=dict(l=0, r=0, b=0),
    title=dict(text='Financing mechanisms: in use vs. wanted'),
  )
  return fig