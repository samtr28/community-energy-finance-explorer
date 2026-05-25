"""
Resources.py — Server module for the Resources page
====================================================
Structure (mirrors Overview.py):
  1. Imports
  2. Main callable                 — get_all_resources_data()
  3. Chart creation functions      — one per chart
  4. Export callable

The display template is applied centrally in get_all_resources_data() via
apply_display_template() from Export_Utils. Add any future resource charts
to the return dict of get_all_resources_data().
"""

import anvil.server
import pandas as pd
import plotly.graph_objects as go
import textwrap

from .Global_Server_Functions import get_data
from .Export_Utils import apply_display_template, export_figure_from_bytes
from .config import dunsparce_colors, FONT_FAMILY


# ==================== MAIN CALLABLE ====================

@anvil.server.callable
def get_all_resources_data():
  """
  Single server call returning all charts for the Resources page.
  Data is loaded once and shared across all chart builders.
  Add future resource charts to this return dict.
  """
  df = get_data()

  return {
    'mechanism_compare': apply_display_template(create_mechanism_compare_internal(df)),
  }


# ==================== CHART CREATION ====================

def create_mechanism_compare_internal(df):
  """
  Grouped horizontal bar chart comparing financing mechanisms currently used
  vs. those respondents want to learn more about. Sorted by 'used'
  (descending), largest bar at top. Annotations mark phrases that weren't
  asked about in one of the two questions.

  Chart-specific: horizontal grouped bars, legend on top, italic
  'No data collected' annotations on missing bars.
  """
  # ── Alias map: collapses different wordings of the same concept ──
  # Keys must be lowercase. Values are the display labels (preserved as-is
  # since first-letter capitalisation is a no-op when already capitalised).
  ALIASES = {
    # grants
    "grants & non-repayable contributions": "grants & non-repayable funding",
    "grants and non-repayable funding":     "grants & non-repayable funding",
    # tax credits
    "tax credits/accelerated depreciation":    "tax credits / accelerated depreciation",
    "tax credits or accelerated depreciation": "tax credits / accelerated depreciation",
    # community finance
    "community-finance models":      "community investment vehicles",
    "community investment vehicles": "community investment vehicles",
    # equity
    "equity investments": "equity financing",
    "equity financing":   "equity financing",
    # internal capital
    "internal/owner-contributed capital": "internal / owner-contributed capital",
    # leasing / PPAs
    "leasing/ppa models":                   "leasing / PPA models",
    "leasing/third-party ownership models": "leasing / PPA models",
    # loan guarantees
    "loan guarantees or credit enhancements": "loan guarantees / credit enhancements",
    "loan guarantees/credit enhancements":    "loan guarantees / credit enhancements",
    # public-private partnerships  — value is the canonical display label
    "public-private partnership (p3)": "Public Private Partnership (P3)",
    "public private partnership (p3)": "Public Private Partnership (P3)",
    "public-private partnerships":     "Public Private Partnership (P3)",
    "public private partnerships":     "Public Private Partnership (P3)",
    "public-private partnership":      "Public Private Partnership (P3)",
    "public private partnership":      "Public Private Partnership (P3)",
    # crowdfunding
    "crowdfunded campaigns":  "crowdfunding campaigns",
    "crowdfunding campaigns": "crowdfunding campaigns",
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
        key = phrase.strip().lower()
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
  # Sort by a numeric column so the bars are actually ordered.
  # Swap 'used' for 'want_to_learn' or 'gap' to order by a different metric.
  plot_data = compare.sort_values('used', ascending=False).reset_index(drop=True)

  # ── Capitalise first letter for display (no-op on already-capitalised labels) ──
  display_labels = [
    '<br>'.join(textwrap.wrap(p[:1].upper() + p[1:], width=25))
    for p in plot_data['phrase']
  ]

  # Per-bar 'No data collected' labels for questions that weren't asked.
  # Attaching the text to the bars (instead of free-floating annotations)
  # lets Plotly place each label at its own bar's grouped offset, so they
  # always line up with the right series regardless of trace order.
  no_data = '<i>No data collected</i>'
  learn_text = [no_data if not asked else '' for asked in plot_data['learn_asked']]
  used_text  = [no_data if not asked else '' for asked in plot_data['used_asked']]

  fig = go.Figure()
  fig.add_trace(go.Bar(
    y=display_labels,
    x=plot_data['want_to_learn'],
    name='Want to learn about',
    orientation='h',
    marker_color=dunsparce_colors[4],
    text=learn_text,
    textposition='outside',
    textfont=dict(family=FONT_FAMILY, size=10, color='gray'),
    cliponaxis=False,
    hovertemplate='<b>%{y}</b><br>Want to learn: %{x}<extra></extra>',
  ))
  fig.add_trace(go.Bar(
    y=display_labels,
    x=plot_data['used'],
    name='Currently used',
    orientation='h',
    marker_color=dunsparce_colors[12],
    text=used_text,
    textposition='outside',
    textfont=dict(family=FONT_FAMILY, size=10, color='gray'),
    cliponaxis=False,
    hovertemplate='<b>%{y}</b><br>Currently used: %{x}<extra></extra>',
  ))

  fig.update_layout(
    barmode='group',
    xaxis_title='Number of responses',
    # categoryarray is reversed because Plotly draws horizontal bars
    # bottom-to-top; reversing puts the largest (first) bar at the top.
    yaxis=dict(
      title='',
      categoryorder='array',
      categoryarray=display_labels[::-1],
    ),
    legend=dict(orientation='h', yanchor='bottom', y=0.99, xanchor='right', x=1),
    margin=dict(l=0, r=0, b=0),
    title=dict(text='Financing Mechanisms: Current Usage vs Future Interest'),
  )

  return fig


# ==================== EXPORT CALLABLE ====================

@anvil.server.callable
def export_mechanism_chart(chart_key, img_b64, active_filters, chart_title=''):
  return export_figure_from_bytes(
    img_b64,
    active_filters,
    filename=f'{chart_key}_export.png',
    chart_title=chart_title,
  )