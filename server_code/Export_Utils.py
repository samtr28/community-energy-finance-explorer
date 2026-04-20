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

# Update the import at the top
from .config import (
FONT_FAMILY, FONT_SIZE, FONT_COLOR,
TITLE_FONT_FAMILY,               # ← add this
TITLE_SIZE, TITLE_PAD_B, MARGIN_TOP
)


# ==================== DISPLAY TEMPLATE ====================
# Applied to every chart before it is sent to the client.
# Centralised here so all pages share the same look automatically.
# To change the app-wide chart style, edit the constants in config.py.

def apply_display_template(fig):
  fig.update_layout(
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR),
    title=dict(
      font=dict(family=TITLE_FONT_FAMILY, size=TITLE_SIZE, color=FONT_COLOR),
      x=0.01, xanchor='left',
      y=0.98, yanchor='top',
      pad=dict(b=TITLE_PAD_B),
    ),
    xaxis=dict(tickfont=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR)),
    yaxis=dict(tickfont=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR)),
    legend=dict(font=dict(family=FONT_FAMILY, size=FONT_SIZE, color=FONT_COLOR)),
    margin=dict(t=MARGIN_TOP),

    # ── Modebar — keep only reset, remove everything else ──
    modebar=dict(
      remove=[
        'toImage', 'zoom2d', 'pan2d', 'select2d',
        'lasso2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d',
      ]
    ),
  )

  for ann in fig.layout.annotations:
    if ann.font.size   is None: ann.font.size   = FONT_SIZE
    if ann.font.family is None: ann.font.family = FONT_FAMILY
    if ann.font.color  is None: ann.font.color  = FONT_COLOR

  return fig


# ==================== EXPORT DECORATION ====================

DEFAULT_LOGO_FILENAME = 'logo.png'

# ── Top banner (filter summary) ──
FILTER_BANNER_HEIGHT  = 50
FILTER_TEXT_SIZE      = 20
FILTER_TEXT_COLOR     = '#222222'
FILTER_TEXT_OFFSET    = (30, 14)   # (x, y) within the top banner

# ── Bottom banner (source + logo) ──
SOURCE_BANNER_HEIGHT  = 100
SOURCE_TEXT           = 'Source: Community Energy Finance Navigator'
SOURCE_TEXT_SIZE      = 16
SOURCE_TEXT_COLOR     = '#555555'
SOURCE_TEXT_OFFSET    = (30, 16)   # (x, y) within the bottom banner

# ── Logo ──
LOGO_MAX_HEIGHT       = 90         # fits neatly in the bottom banner
LOGO_PADDING          = 10         # px from right and bottom edges of banner


def _load_font(size):
  """Load DejaVu Sans at the given size, fall back to Pillow default."""
  try:
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', size)
  except Exception:
    return ImageFont.load_default()


def _build_filter_text(active_filters):
  """Format active filters dict into a single annotation string."""
  parts = [f"{k}: {v}" for k, v in active_filters.items() if v != 'All']
  return 'Filters applied — ' + ('   |   '.join(parts) if parts else 'None')


def add_logo_and_filters_pil(img_bytes, active_filters, logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Decorate a raw PNG with:
    - A top banner showing the active filter summary (larger text)
    - A bottom banner showing the data source and logo (bottom-right)
  Returns the decorated PNG as bytes.
  """
  img   = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
  w, h  = img.size
  total = h + FILTER_BANNER_HEIGHT + SOURCE_BANNER_HEIGHT

  # ── Build canvas: top banner + chart + bottom banner ──
  canvas = Image.new('RGBA', (w, total), 'white')
  canvas.paste(img, (0, FILTER_BANNER_HEIGHT))   # chart sits below the top banner
  draw = ImageDraw.Draw(canvas)

  # ── Top banner: filter summary ──
  draw.text(
    (FILTER_TEXT_OFFSET[0], FILTER_TEXT_OFFSET[1]),
    _build_filter_text(active_filters),
    fill=FILTER_TEXT_COLOR,
    font=_load_font(FILTER_TEXT_SIZE)
  )

  # ── Bottom banner: source text ──
  source_y = FILTER_BANNER_HEIGHT + h + SOURCE_TEXT_OFFSET[1]
  draw.text(
    (SOURCE_TEXT_OFFSET[0], source_y),
    SOURCE_TEXT,
    fill=SOURCE_TEXT_COLOR,
    font=_load_font(SOURCE_TEXT_SIZE)
  )

  # ── Bottom banner: logo bottom-right ──
  try:
    logo  = Image.open(data_files[logo_filename]).convert('RGBA')
    ratio = LOGO_MAX_HEIGHT / logo.height
    logo  = logo.resize((int(logo.width * ratio), LOGO_MAX_HEIGHT), Image.LANCZOS)
    x     = w - logo.width - LOGO_PADDING
    y     = FILTER_BANNER_HEIGHT + h + (SOURCE_BANNER_HEIGHT - logo.height) // 2
    canvas.paste(logo, (x, y), logo)
  except Exception as e:
    print(f"Logo skipped: {e}")

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