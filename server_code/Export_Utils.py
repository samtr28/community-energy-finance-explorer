"""
Export_Utils.py — Server module
================================
Two responsibilities:
  1. apply_display_template(fig) — consistent visual style for all Plotly figures
  2. export_figure_from_bytes()  — decorates captured PNG for download

Export layout:
  ┌─[COLOURED BANNER]──────────────────────────[  LOGO  ]─┐
  │  Community Energy Finance Navigator                    │  ← large bold heading
  │                                                        │
  │  Filters applied —                                     │
  │  Project Scale: Small   |   Province: BC               │  ← bottom of banner
  ├────────────────────────────────────────────────────────┤
  │                      chart                             │
  ├────────────────────────────────────────────────────────┤
  │  Data reflects survey responses...    April 20, 2026   │  ← bottom strip
  └────────────────────────────────────────────────────────┘

Usage in any page server module:
    from .Export_Utils import export_figure_from_bytes, apply_display_template
"""

import anvil.server
import anvil.media
import base64
import io
from datetime import date
from anvil.files import data_files
from PIL import Image, ImageDraw, ImageFont

from .config import (
FONT_FAMILY, FONT_SIZE, FONT_COLOR,
TITLE_FONT_FAMILY, TITLE_SIZE, TITLE_PAD_B, MARGIN_TOP
)


# ==================== DISPLAY TEMPLATE ====================

def apply_display_template(fig):
  """
  Apply a consistent visual style to any Plotly figure.

  Sets: transparent backgrounds, distinctive title font, uniform base font,
  top margin, and a stripped-down modebar (reset only).
  Annotation fonts are only set where not already explicitly defined,
  preserving intentional per-annotation overrides.
  """
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

# ── Banner background ──
# Light tint of the brand dark blue. Change here to restyle all exports.
BANNER_BG_COLOR  = '#f0f0f0'

# ── Logo (top-right of banner) ──
LOGO_MAX_HEIGHT  = 200             # px
LOGO_MAX_WIDTH   = 500             # px — cap for wide landscape logos
LOGO_PADDING     = 20              # px from right and top edges

# ── Source heading (top-left of banner) ──
SOURCE_TEXT       = 'Community Energy Finance Navigator'
SOURCE_TEXT_SIZE  = 36             # pt
SOURCE_TEXT_COLOR = '#002754'      # brand navy
SOURCE_TOP_MARGIN = 24             # px from top of banner

# ── Filter text (bottom of banner, directly above chart) ──
FILTER_HEADER_SIZE = 18            # pt
FILTER_VALUE_SIZE  = 16            # pt
FILTER_TEXT_COLOR  = '#1a1a1a'
FILTER_LEFT_MARGIN = 30            # px from left edge
FILTER_BOTTOM_PAD  = 18            # px gap between last filter line and chart

# ── Bottom strip (disclaimer + date) ──
BOTTOM_STRIP_HEIGHT = 52           # px
BOTTOM_STRIP_HEIGHT = 52           # px
BOTTOM_STRIP_HEIGHT = 52           # px
DISCLAIMER_TEXT     = 'Data reflects survey responses collected as part of ongoing research. For informational purposes only.'
DISCLAIMER_SIZE     = 15           # pt
DISCLAIMER_COLOR    = '#777777'
DATE_SIZE           = 15           # pt
DATE_COLOR          = '#777777'
STRIP_PADDING       = 14           # px from edges of strip

# ── Minimum banner height ──
BANNER_MIN_HEIGHT   = 140          # px


def _load_font(size, bold=False):
  """Load DejaVu Sans (bold or regular) at the given pt size."""
  try:
    path = (
      '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
      else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    )
    return ImageFont.truetype(path, size)
  except Exception:
    return ImageFont.load_default()


def _resize_logo(logo, max_h, max_w):
  """Resize a PIL image to fit within max_h × max_w, preserving aspect ratio."""
  ratio = min(max_h / logo.height, max_w / logo.width)
  return logo.resize((int(logo.width * ratio), int(logo.height * ratio)), Image.LANCZOS)


def _build_filter_lines(active_filters):
  """Return (bold_label, regular_value) tuples for filters where value != 'All'."""
  return [(f"{k}:", v) for k, v in active_filters.items() if v != 'All']


def add_logo_and_filters_pil(img_bytes, active_filters, chart_title='', logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Decorate a raw PNG with a coloured top banner and a plain bottom strip.

  Top banner (coloured background):
    - Source heading: large bold, top-left
    - Logo: top-right
    - Filters: bottom-aligned directly above the chart
      Filter keys are bold; values are regular weight.

  Bottom strip (white background):
    - Disclaimer text: left-aligned
    - Export date: right-aligned

  Returns the decorated PNG as bytes.
  """
  img  = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
  w, h = img.size

  # ── Load and resize logo ──
  logo = None
  logo_w, logo_h = 0, 0
  try:
    logo = _resize_logo(
      Image.open(data_files[logo_filename]).convert('RGBA'),
      LOGO_MAX_HEIGHT, LOGO_MAX_WIDTH
    )
    logo_w, logo_h = logo.size
  except Exception as e:
    print(f"Logo skipped: {e}")

  # ── Calculate banner height ──
  filter_lines   = _build_filter_lines(active_filters)
  line_height    = FILTER_VALUE_SIZE + 8
  filter_block_h = (
    FILTER_HEADER_SIZE + 10
    + len(filter_lines) * line_height
    + FILTER_BOTTOM_PAD
  )
  text_stack_h = (
    SOURCE_TOP_MARGIN
    + SOURCE_TEXT_SIZE
    + 16                  # gap between heading and filter block
    + filter_block_h
  )
  banner_h = max(
    logo_h + LOGO_PADDING * 2,
    text_stack_h,
    BANNER_MIN_HEIGHT
  )

  total_h = banner_h + h + BOTTOM_STRIP_HEIGHT

  # ── Build canvas ──
  canvas = Image.new('RGBA', (w, total_h), 'white')

  # Coloured banner background
  canvas.paste(Image.new('RGBA', (w, banner_h), BANNER_BG_COLOR), (0, 0))

  # Chart image
  canvas.paste(img, (0, banner_h))

  draw = ImageDraw.Draw(canvas)

  # ── Source heading: top-left ──
  draw.text(
    (FILTER_LEFT_MARGIN, SOURCE_TOP_MARGIN),
    chart_title,
    fill=SOURCE_TEXT_COLOR,
    font=_load_font(SOURCE_TEXT_SIZE, bold=True)
  )

  # ── Logo: top-right ──
  if logo:
    canvas.paste(logo, (w - logo_w - LOGO_PADDING, LOGO_PADDING), logo)

  # ── Filters: bottom-aligned within the banner ──
  font_header = _load_font(FILTER_HEADER_SIZE, bold=True)
  font_bold   = _load_font(FILTER_VALUE_SIZE,  bold=True)
  font_reg    = _load_font(FILTER_VALUE_SIZE,  bold=False)

  cursor_y = (
    banner_h
    - FILTER_BOTTOM_PAD
    - len(filter_lines) * line_height
    - (FILTER_HEADER_SIZE + 10)
  )

  draw.text(
    (FILTER_LEFT_MARGIN, cursor_y),
    'Filters applied —' if filter_lines else 'Filters applied — None',
    fill=FILTER_TEXT_COLOR,
    font=font_header
  )
  cursor_y += FILTER_HEADER_SIZE + 10

  for label, value in filter_lines:
    draw.text((FILTER_LEFT_MARGIN, cursor_y), label, fill=FILTER_TEXT_COLOR, font=font_bold)
    label_w = draw.textlength(label, font=font_bold)
    draw.text(
      (FILTER_LEFT_MARGIN + label_w + 6, cursor_y),
      value,
      fill=FILTER_TEXT_COLOR,
      font=font_reg
    )
    cursor_y += line_height

  # ── Bottom strip: disclaimer left, date right ──
  font_small  = _load_font(DISCLAIMER_SIZE)
  strip_text_y = banner_h + h + STRIP_PADDING

  draw.text(
    (STRIP_PADDING, strip_text_y),
    DISCLAIMER_TEXT,
    fill=DISCLAIMER_COLOR,
    font=font_small
  )

  date_str = date.today().strftime('%B %-d, %Y')
  date_w   = draw.textlength(date_str, font=font_small)
  draw.text(
    (w - date_w - STRIP_PADDING, strip_text_y),
    date_str,
    fill=DATE_COLOR,
    font=font_small
  )

  # ── Convert to RGB PNG bytes ──
  out = io.BytesIO()
  canvas.convert('RGB').save(out, format='PNG')
  return out.getvalue()


# ==================== PUBLIC ENTRY POINT ====================

def export_figure_from_bytes(img_b64, active_filters, filename='chart_export.png',
                               chart_title='', logo_filename=DEFAULT_LOGO_FILENAME):
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
    base64.b64decode(img_b64), active_filters, chart_title=chart_title, logo_filename=logo_filename
  )
  return anvil.BlobMedia('image/png', decorated, name=filename)