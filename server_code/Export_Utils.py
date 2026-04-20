"""
Export_Utils.py — Server module
================================
Two responsibilities:
  1. apply_display_template(fig) — applies consistent visual style to any
     Plotly figure before it is sent to the client. Used by all page server modules.
  2. export_figure_from_bytes()  — decorates a client-captured PNG with the
     logo and active filter summary, returns BlobMedia for download.

Usage in any page server module:
    from .Export_Utils import export_figure_from_bytes, apply_display_template
"""

import anvil.server
import anvil.media
import base64
import io
from anvil.files import data_files
from PIL import Image, ImageDraw, ImageFont

from .config import (
FONT_FAMILY, FONT_SIZE, FONT_COLOR,
TITLE_SIZE, TITLE_PAD_B, MARGIN_TOP
)


# ==================== DISPLAY TEMPLATE ====================
# Applied to every chart before it is sent to the client.
# Centralised here so all pages share the same look automatically.
# To change the app-wide chart style, edit the constants in config.py.

def apply_display_template(fig):
  """
  Apply a consistent visual style to any Plotly figure.

  What it sets:
    - Transparent background (blends with the app theme)
    - Title: larger, clearly separated from the plot by padding
    - Base font: uniform size across tick labels, legend, hover text
    - Top margin: enough room for the title
    - Annotation fonts: base font applied only where not already set
      (preserves intentional overrides such as the white lollipop counts)

  Call this on every figure in the main callable, after building it,
  before adding it to the results dict. Per-chart specifics (axis
  visibility, bar modes, colours) are set inside the chart functions
  themselves and are not touched here.
  """
  fig.update_layout(
    # ── Backgrounds ──
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',

    # ── Base font — cascades to tick labels, legend, hover ──
    font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),

    # ── Title — prominent and clearly separated from the chart ──
    title=dict(
      font=dict(family=FONT_FAMILY, size=TITLE_SIZE, color=FONT_COLOR),
      x=0.01, xanchor='left',
      y=0.98, yanchor='top',
      pad=dict(b=TITLE_PAD_B),
    ),

    # ── Axes — ensure tick font matches base size ──
    xaxis=dict(tickfont=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR)),
    yaxis=dict(tickfont=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR)),

    # ── Legend ──
    legend=dict(font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR)),

    # ── Top margin — room for the title ──
    margin=dict(t=MARGIN_TOP),
  )

  # Apply base font to annotations only where not explicitly overridden.
  # This preserves intentional per-annotation styles (e.g. white lollipop
  # count numbers, dark teal category labels).
  for ann in fig.layout.annotations:
    if ann.font.size   is None: ann.font.size   = FONT_SIZE
    if ann.font.family is None: ann.font.family = FONT_FAMILY
    if ann.font.color  is None: ann.font.color  = FONT_COLOR

  return fig


# ==================== EXPORT DECORATION ====================
# Configuration — edit these to adjust the exported PNG appearance.

DEFAULT_LOGO_FILENAME  = 'logo.png'   # must match filename in Anvil Assets exactly
FILTER_BANNER_HEIGHT   = 60           # px added below chart for filter text
LOGO_MAX_HEIGHT        = 60           # logo resized to this height (px), width proportional
LOGO_PADDING           = 10           # px padding from top-right corner
FILTER_TEXT_COLOR      = '#555555'
FILTER_TEXT_SIZE       = 18           # pt
FILTER_TEXT_OFFSET     = (30, 15)     # (x, y) within the banner


def _load_font(size=FILTER_TEXT_SIZE):
  """Load DejaVu Sans if available on the server, fall back to Pillow default."""
  try:
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', size)
  except Exception:
    return ImageFont.load_default()


def _build_filter_text(active_filters):
  """Format active filters dict into a single annotation string."""
  parts = [f"{k}: {v}" for k, v in active_filters.items() if v != 'All']
  return 'Filters: ' + ('   |   '.join(parts) if parts else 'No filters applied')


def _stamp_logo(canvas, logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Load logo from Anvil Assets, resize it, and paste into the top-right
  corner of the canvas. Fails silently if the logo file is not found.
  """
  try:
    logo = Image.open(data_files[logo_filename]).convert('RGBA')
    ratio = LOGO_MAX_HEIGHT / logo.height
    logo  = logo.resize((int(logo.width * ratio), LOGO_MAX_HEIGHT), Image.LANCZOS)
    canvas.paste(logo, (canvas.width - logo.width - LOGO_PADDING, LOGO_PADDING), logo)
  except Exception as e:
    print(f"Logo skipped: {e}")
  return canvas


def add_logo_and_filters_pil(img_bytes, active_filters, logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Decorate a raw PNG (as bytes) with a white filter-text banner and the app logo.
  Returns the decorated PNG as bytes.
  """
  img    = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
  w, h   = img.size

  # New canvas = original height + banner
  canvas = Image.new('RGBA', (w, h + FILTER_BANNER_HEIGHT), 'white')
  canvas.paste(img, (0, 0))

  # Filter text in the banner
  draw = ImageDraw.Draw(canvas)
  draw.text(
    (FILTER_TEXT_OFFSET[0], h + FILTER_TEXT_OFFSET[1]),
    _build_filter_text(active_filters),
    fill=FILTER_TEXT_COLOR,
    font=_load_font()
  )

  # Logo top-right
  canvas = _stamp_logo(canvas, logo_filename)

  out = io.BytesIO()
  canvas.convert('RGB').save(out, format='PNG')
  return out.getvalue()


def export_figure_from_bytes(img_b64, active_filters, filename='chart_export.png',
                             logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Entry point called by every page's export server callable.

  Args:
    img_b64:        base64-encoded PNG string captured by the browser
    active_filters: dict of human-readable filter label → value strings
    filename:       download filename for the output PNG
    logo_filename:  Anvil Asset filename for the logo

  Returns:
    anvil.BlobMedia ready for anvil.download() on the client
  """
  decorated = add_logo_and_filters_pil(
    base64.b64decode(img_b64), active_filters, logo_filename
  )
  return anvil.BlobMedia('image/png', decorated, name=filename)