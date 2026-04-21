"""
chart_export.py — Client-side chart export module
==================================================
Reusable across all pages. Import and call download_chart() from any form.

Usage in a form:
    from ..chart_export import download_chart

    def download_my_chart_click(self, **event_args):
        download_chart(
            plot_component=self.my_plot,
            chart_key='my_chart',
            active_filters=self._get_active_filters(),
            server_callable='export_my_page_chart',
            button=self.download_btn   # optional — shows "Downloading..." feedback
        )
"""

import anvil.server
from anvil.js import window, get_dom_node, await_promise


# ==================== EXPORT APPEARANCE ====================
# Applied to the figure at export time only — never affects the displayed chart.
# Add or remove any valid Plotly layout keys here to adjust the export style.

EXPORT_TEMPLATE = {
  'paper_bgcolor':    'white',
  'plot_bgcolor':     '#f8f8f8',
  'font.family':      'Arial, sans-serif',
  'font.size':        13,
  'font.color':       '#333333',
  'title.text':       '',           # ← add this — title shown in banner instead
  'title.font.size':  18,
  'title.font.color': '#1a1a1a',
  'xaxis.gridcolor':  '#e0e0e0',
  'xaxis.linecolor':  '#cccccc',
  'yaxis.gridcolor':  '#e0e0e0',
  'yaxis.linecolor':  '#cccccc',
}


# ==================== EXPORT IMAGE SETTINGS ====================
# Adjust width, height, and scale (scale=2 gives a high-res 2400x1400px output).

EXPORT_CONFIG = {
  'format': 'png',
  'width':  1200,
  'height': 700,
  'scale':  2,
}


# ==================== CORE EXPORT FUNCTION ====================

def download_chart(plot_component, chart_key, active_filters, server_callable, button=None):
  """
  Capture any anvil.Plot component as a decorated PNG and download it.

  Steps:
    1. Optionally shows "Downloading..." feedback on the button
    2. Reads the chart's current data and layout from the DOM
    3. Merges EXPORT_TEMPLATE into a copy of the layout (never modifies the display)
    4. Passes the figure object to Plotly.toImage() — no relayout, no flicker
    5. Sends the base64 PNG to the server for logo + filter decoration
    6. Triggers anvil.download() with the returned BlobMedia

  Args:
    plot_component:  anvil.Plot instance (e.g. self.box_plot)
    chart_key:       string key identifying the chart (e.g. 'box_plot')
    active_filters:  dict of human-readable filter values for the export annotation
    server_callable: name of the server function to call (e.g. 'export_capital_chart')
    button:          optional Button component — shows loading state during export
  """

  # ── Optional button feedback ──
  if button:
    original_text   = button.text
    button.enabled  = False
    button.text     = "Downloading..."

  # ── Build export figure without touching the DOM ──
  node = get_dom_node(plot_component)

  # ── Read chart title directly from the figure ──
  chart_title = ''
  try:
    chart_title = node.layout.title.text or ''
  except Exception:
    pass

  export_layout = dict(node.layout)       # copy current layout
  export_layout.update(EXPORT_TEMPLATE)   # overlay export styling

  figure = {
    'data':   node.data,      # traces unchanged
    'layout': export_layout   # styled layout copy
  }

  # ── Capture PNG via Plotly.toImage ──
  img_data_url = await_promise(
    window.Plotly.toImage(figure, EXPORT_CONFIG)
  )
  img_b64 = img_data_url.split(',')[1]   # strip 'data:image/png;base64,' prefix

  # ── Send to server for logo + filter decoration, then download ──
  # call_s = silent call, suppresses Anvil's loading spinner
  media = anvil.server.call_s(server_callable, chart_key, img_b64, active_filters, chart_title)
  anvil.download(media)

  # ── Restore button ──
  if button:
    button.text    = original_text
    button.enabled = True