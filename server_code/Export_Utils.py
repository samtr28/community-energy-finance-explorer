"""
Export_Utils.py — Server module
================================
Two responsibilities:
  1. apply_display_template(fig) — consistent visual style for all Plotly figures
  2. export_figure_from_bytes()  — decorates captured PNG for download

Export layout:
  ┌─────────────────────────────────────────────────────────┐
  │  Average Time to Funding                                │  ← chart title (large bold)
  │  Survey-based data on 47 projects as of April 21, 2026  │  ← subtitle
  │  Filters applied —                                      │
  │  Project Scale: Small   |   Province: BC                │  ← filters (bottom of banner)
  ├─────────────────────────────────────────────────────────┤
  │                        chart                            │
  ├─────────────────────────────────────────────────────────┤
  │  Source: Community Energy Finance Navigator, UVic  [LOGO]│  ← bottom strip
  └─────────────────────────────────────────────────────────┘

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

# ── Banner (white background) ──
BANNER_BG_COLOR     = '#ffffff'

# ── Chart title (top of banner) ──
CHART_TITLE_SIZE    = 26           # pt — large and prominent
CHART_TITLE_COLOR   = '#002754'    # brand navy
CHART_TITLE_TOP     = 24           # px from top of banner

# ── Subtitle: "Survey-based data on X projects as of DATE" ──
SUBTITLE_SIZE       = 16           # pt
SUBTITLE_COLOR      = '#444444'
SUBTITLE_GAP        = 10           # px below chart title

# ── Filter text (bottom of banner, directly above chart) ──
FILTER_HEADER_SIZE  = 16           # pt
FILTER_VALUE_SIZE   = 15           # pt
FILTER_TEXT_COLOR   = '#1a1a1a'
FILTER_LEFT_MARGIN  = 30           # px from left edge
FILTER_BOTTOM_PAD   = 18           # px gap between last filter line and chart
FILTER_GAP_FROM_SUB = 14           # px between subtitle and filters header

# ── Minimum banner height ──
BANNER_MIN_HEIGHT   = 120          # px

# ── Bottom strip (source + logo) ──
BOTTOM_STRIP_HEIGHT = 60           # px — tall enough for the logo
SOURCE_TEXT         = 'Source: Community Energy Finance Navigator, University of Victoria'
SOURCE_TEXT_SIZE    = 15           # pt
SOURCE_TEXT_COLOR   = '#555555'
STRIP_PADDING       = 14           # px from edges

# ── Logo (bottom strip, right-aligned, vertically centred) ──
LOGO_MAX_HEIGHT     = 40           # px — fits neatly in the strip
LOGO_MAX_WIDTH      = 200          # px
LOGO_STRIP_PADDING  = 14           # px from right edge


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


def add_logo_and_filters_pil(img_bytes, active_filters, chart_title='',
                             project_count=None, logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Decorate a raw PNG with a top banner and a bottom strip.

  Top banner (white background):
    - Chart title: large bold, top-left
    - Subtitle: "Survey-based data on X projects as of DATE"
    - Filters: bottom-aligned, directly above the chart
      Filter keys are bold; values are regular weight.

  Bottom strip:
    - Source citation: left-aligned, vertically centred
    - Logo: right-aligned, vertically centred

  Returns the decorated PNG as bytes.
  """
  img  = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
  w, h = img.size

  # ── Fonts ──
  font_title    = _load_font(CHART_TITLE_SIZE,  bold=True)
  font_subtitle = _load_font(SUBTITLE_SIZE,      bold=False)
  font_filter_h = _load_font(FILTER_HEADER_SIZE, bold=True)
  font_bold     = _load_font(FILTER_VALUE_SIZE,  bold=True)
  font_reg      = _load_font(FILTER_VALUE_SIZE,  bold=False)
  font_source   = _load_font(SOURCE_TEXT_SIZE,   bold=False)

  # ── Calculate banner height ──
  filter_lines   = _build_filter_lines(active_filters)
  line_height    = FILTER_VALUE_SIZE + 8
  filter_block_h = (
    FILTER_HEADER_SIZE + 10
    + len(filter_lines) * line_height
    + FILTER_BOTTOM_PAD
  )
  text_stack_h = (
    CHART_TITLE_TOP
    + CHART_TITLE_SIZE
    + SUBTITLE_GAP
    + SUBTITLE_SIZE
    + FILTER_GAP_FROM_SUB
    + filter_block_h
  )
  banner_h = max(text_stack_h, BANNER_MIN_HEIGHT)

  total_h = banner_h + h + BOTTOM_STRIP_HEIGHT

  # ── Build canvas ──
  canvas = Image.new('RGBA', (w, total_h), 'white')
  canvas.paste(Image.new('RGBA', (w, banner_h), BANNER_BG_COLOR), (0, 0))
  canvas.paste(img, (0, banner_h))
  draw = ImageDraw.Draw(canvas)

  # ── Chart title ──
  draw.text(
    (FILTER_LEFT_MARGIN, CHART_TITLE_TOP),
    chart_title,
    fill=CHART_TITLE_COLOR,
    font=font_title
  )

  # ── Subtitle ──
  today_str   = date.today().strftime('%B %-d, %Y')
  count_str   = str(project_count) if project_count is not None else '—'
  subtitle    = f'Survey-based data on {count_str} projects as of {today_str}'
  subtitle_y  = CHART_TITLE_TOP + CHART_TITLE_SIZE + SUBTITLE_GAP
  draw.text(
    (FILTER_LEFT_MARGIN, subtitle_y),
    subtitle,
    fill=SUBTITLE_COLOR,
    font=font_subtitle
  )

  # ── Filters: bottom-aligned within the banner ──
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
    font=font_filter_h
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

  # ── Bottom strip: source left, logo right ──
  strip_y = banner_h + h

  # Load and resize logo for strip
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

  # Source text — vertically centred in strip
  source_text_y = strip_y + (BOTTOM_STRIP_HEIGHT - SOURCE_TEXT_SIZE) // 2
  draw.text(
    (STRIP_PADDING, source_text_y),
    SOURCE_TEXT,
    fill=SOURCE_TEXT_COLOR,
    font=font_source
  )

  # Logo — vertically centred, right-aligned
  if logo:
    lx = w - logo_w - LOGO_STRIP_PADDING
    ly = strip_y + (BOTTOM_STRIP_HEIGHT - logo_h) // 2
    canvas.paste(logo, (lx, ly), logo)

  # ── Convert to RGB PNG bytes ──
  out = io.BytesIO()
  canvas.convert('RGB').save(out, format='PNG')
  return out.getvalue()


# ==================== PUBLIC ENTRY POINT ====================

def export_figure_from_bytes(img_b64, active_filters, filename='chart_export.png',
                             chart_title='', project_count=None,
                             logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Entry point called by every page's export server callable.

  Args:
    img_b64:        base64-encoded PNG string captured by the browser
    active_filters: dict of human-readable filter label → value strings
    filename:       download filename for the output PNG
    chart_title:    title string displayed at the top of the export banner
    project_count:  number of projects in the current filtered dataset
    logo_filename:  Anvil Asset filename for the logo

  Returns:
    anvil.BlobMedia ready for anvil.download() on the client
  """
  decorated = add_logo_and_filters_pil(
    base64.b64decode(img_b64),
    active_filters,
    chart_title=chart_title,
    project_count=project_count,
    logo_filename=logo_filename
  )
  return anvil.BlobMedia('image/png', decorated, name=filename)