"""
Export_Utils.py — Server module
================================
Two responsibilities:
  1. apply_display_template(fig) — consistent visual style for all Plotly figures
  2. export_figure_from_bytes()  — decorates captured PNG for download

Export layout:
  ┌─[LIGHT GREY BANNER]────────────────────────────────────┐
  │  Average Time to Funding                               │  ← chart title (large bold)
  │  Survey-based data downloaded on April 21, 2026        │  ← subtitle
  │  Filters applied — Scale: Small   |   Province: BC     │  ← all on one line
  ├────────────────────────────────────────────────────────┤
  │                      chart (no title)                  │
  ├────────────────────────────────────────────────────────┤
  │  Source: Community Energy Finance Navigator, UVic [LOGO]│  ← bottom strip
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

# ── Banner (top section, light grey) ──
BANNER_BG_COLOR    = '#f0f0f0'
LEFT_MARGIN        = 30            # px from left edge throughout banner
BANNER_TOP_PAD     = 24            # px from top of banner to first line
LINE_SPACING       = 12            # px between each text line in the banner
BANNER_BOTTOM_PAD  = 20            # px below last line before chart

# ── Chart title ──
TITLE_TEXT_SIZE    = 28            # pt
TITLE_TEXT_COLOR   = '#002754'     # brand navy

# ── Subtitle ──
SUBTITLE_SIZE      = 16            # pt
SUBTITLE_COLOR     = '#444444'

# ── Filters line ──
FILTER_SIZE        = 15            # pt
FILTER_TEXT_COLOR  = '#1a1a1a'
FILTER_SEPARATOR   = '   |   '     # separator between filter values on one line

# ── Bottom strip (source + large logo) ──
LOGO_MAX_HEIGHT    = 200           # px
LOGO_MAX_WIDTH     = 500           # px
STRIP_PADDING      = 20            # px inside strip
BOTTOM_STRIP_HEIGHT = LOGO_MAX_HEIGHT + STRIP_PADDING * 2   # auto-sizes to logo

SOURCE_TEXT        = 'Source: Community Energy Finance Navigator, University of Victoria'
SOURCE_TEXT_SIZE   = 17            # pt
SOURCE_TEXT_COLOR  = '#444444'


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
  """Resize a PIL image to fit within max_h x max_w, preserving aspect ratio."""
  ratio = min(max_h / logo.height, max_w / logo.width)
  return logo.resize((int(logo.width * ratio), int(logo.height * ratio)), Image.LANCZOS)


def _build_filter_line(active_filters):
  """
  Build a single line string of all active filters.
  e.g. "Filters applied — Scale: Small   |   Province: BC"
  Returns empty string if no filters are active.
  """
  parts = [f"{k}: {v}" for k, v in active_filters.items() if v != 'All']
  if not parts:
    return 'Filters applied — None'
  return 'Filters applied — ' + FILTER_SEPARATOR.join(parts)


def add_logo_and_filters_pil(img_bytes, active_filters, chart_title='',
                             logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Decorate a raw PNG with a top banner and a bottom strip.

  Top banner (light grey, top-down layout):
    Line 1: Chart title (large bold)
    Line 2: Survey-based data downloaded on DATE
    Line 3: Filters applied — key: val | key: val  (all on one line)

  Bottom strip (white, tall):
    Source citation left, large logo right, both vertically centred.

  Returns the decorated PNG as bytes.
  """
  img  = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
  w, h = img.size

  # ── Fonts ──
  font_title    = _load_font(TITLE_TEXT_SIZE, bold=True)
  font_subtitle = _load_font(SUBTITLE_SIZE,   bold=False)
  font_filter   = _load_font(FILTER_SIZE,     bold=False)
  font_source   = _load_font(SOURCE_TEXT_SIZE, bold=False)

  # ── Calculate banner height (top-down stack) ──
  banner_h = (
    BANNER_TOP_PAD
    + TITLE_TEXT_SIZE  + LINE_SPACING
    + SUBTITLE_SIZE    + LINE_SPACING
    + FILTER_SIZE      + BANNER_BOTTOM_PAD
  )

  total_h = banner_h + h + BOTTOM_STRIP_HEIGHT

  # ── Build canvas ──
  canvas = Image.new('RGBA', (w, total_h), 'white')
  canvas.paste(Image.new('RGBA', (w, banner_h), BANNER_BG_COLOR), (0, 0))
  canvas.paste(img, (0, banner_h))
  draw = ImageDraw.Draw(canvas)

  # ── Draw banner lines top-down ──
  cursor_y = BANNER_TOP_PAD

  # Line 1: chart title
  draw.text(
    (LEFT_MARGIN, cursor_y),
    chart_title,
    fill=TITLE_TEXT_COLOR,
    font=font_title
  )
  cursor_y += TITLE_TEXT_SIZE + LINE_SPACING

  # Line 2: subtitle
  today_str = date.today().strftime('%B %-d, %Y')
  draw.text(
    (LEFT_MARGIN, cursor_y),
    f'Survey-based data downloaded on {today_str}',
    fill=SUBTITLE_COLOR,
    font=font_subtitle
  )
  cursor_y += SUBTITLE_SIZE + LINE_SPACING

  # Line 3: filters — all on one line
  draw.text(
    (LEFT_MARGIN, cursor_y),
    _build_filter_line(active_filters),
    fill=FILTER_TEXT_COLOR,
    font=font_filter
  )

  # ── Bottom strip: source left, large logo right ──
  strip_y = banner_h + h

  # Source text — vertically centred
  source_text_y = strip_y + (BOTTOM_STRIP_HEIGHT - SOURCE_TEXT_SIZE) // 2
  draw.text(
    (STRIP_PADDING, source_text_y),
    SOURCE_TEXT,
    fill=SOURCE_TEXT_COLOR,
    font=font_source
  )

  # Large logo — vertically centred, right-aligned
  try:
    logo = _resize_logo(
      Image.open(data_files[logo_filename]).convert('RGBA'),
      LOGO_MAX_HEIGHT, LOGO_MAX_WIDTH
    )
    lw, lh = logo.size
    canvas.paste(logo, (w - lw - STRIP_PADDING, strip_y + (BOTTOM_STRIP_HEIGHT - lh) // 2), logo)
  except Exception as e:
    print(f"Logo skipped: {e}")

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
    chart_title:    title string read from the figure by the client
    logo_filename:  Anvil Asset filename for the logo

  Returns:
    anvil.BlobMedia ready for anvil.download() on the client
  """
  decorated = add_logo_and_filters_pil(
    base64.b64decode(img_b64),
    active_filters,
    chart_title=chart_title,
    logo_filename=logo_filename
  )
  return anvil.BlobMedia('image/png', decorated, name=filename)