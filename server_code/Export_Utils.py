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
  │  Filters applied —                                     │  ← bold prefix
  │  Scale: Small   |   Province: BC   |   Stage: Plan     │  ← wrapped filter values
  ├────────────────────────────────────────────────────────┤
  │   [white padding]                                      │
  │       chart image (no title)                           │
  │   [white padding]                                      │
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
  Annotation fonts only set where not already explicitly defined.
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

# ── Chart padding — white space around the chart image ──
CHART_PADDING_H     = 40           # px left and right of chart
CHART_PADDING_V     = 5            # px above and below chart

# ── Banner (top section, light grey) ──
BANNER_BG_COLOR     = '#f0f0f0'
LEFT_MARGIN         = 30           # px from left edge
BANNER_TOP_PAD      = 24           # px from top of banner to first line
LINE_SPACING        = 12           # px between each text line
BANNER_BOTTOM_PAD   = 20           # px below last line before chart padding

# ── Chart title ──
TITLE_TEXT_SIZE     = 45           # pt
TITLE_TEXT_COLOR    = '#002754'    # brand navy

# ── Subtitle ──
SUBTITLE_SIZE       = 30           # pt
SUBTITLE_COLOR      = '#444444'

# ── Filter line ──
# "Filters applied —" is bold; all keys and values are regular weight.
# If the full line exceeds the available width it wraps:
#   Line 1: "Filters applied —"
#   Line 2+: each filter on its own indented line
FILTER_SIZE         = 18           # pt
FILTER_TEXT_COLOR   = '#1a1a1a'
FILTER_SEPARATOR    = '   |   '    # separator between entries on the same line

# ── Bottom strip ──
LOGO_MAX_HEIGHT     = 150          # px
LOGO_MAX_WIDTH      = 500          # px
STRIP_PADDING       = 20           # px inside strip
BOTTOM_STRIP_HEIGHT = LOGO_MAX_HEIGHT + STRIP_PADDING * 2

SOURCE_TEXT         = 'Source: Community Energy Finance Navigator, University of Victoria'
SOURCE_TEXT_SIZE    = 20           # pt
SOURCE_TEXT_COLOR   = '#444444'


def _load_font(size, bold=False):
  """Load DejaVu Sans bold or regular at the given pt size."""
  try:
    path = (
      '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
      else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    )
    return ImageFont.truetype(path, size)
  except Exception:
    try:
      path = (
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf' if bold
        else '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
      )
      return ImageFont.truetype(path, size)
    except Exception:
      return ImageFont.load_default()


def _resize_logo(logo, max_h, max_w):
  """Resize a PIL image to fit within max_h x max_w, preserving aspect ratio."""
  ratio = min(max_h / logo.height, max_w / logo.width)
  return logo.resize((int(logo.width * ratio), int(logo.height * ratio)), Image.LANCZOS)


def _measure_filter_line(draw, parts, font_bold, font_reg, separator):
  """Measure the total pixel width of the full filter line if drawn on one line."""
  prefix_w = draw.textlength('Filters applied — ', font=font_bold)
  parts_w  = sum(
    draw.textlength(label, font=font_reg) +
    draw.textlength(' ' + value, font=font_reg) +
    (draw.textlength(separator, font=font_reg) if i < len(parts) - 1 else 0)
    for i, (label, value) in enumerate(parts)
  )
  return prefix_w + parts_w


def _draw_filter_text(draw, x, y, active_filters, font_bold, font_reg,
                      color, separator, max_width):
  """
  Draw the filter summary, wrapping if necessary.

  If everything fits on one line:
    "Filters applied — Scale: Small   |   Province: BC"
     ^bold              ^regular throughout

  If too wide:
    "Filters applied —"      ← bold prefix on its own line
    "Scale: Small   |   Province: BC   |   ..."   ← filters on next line(s)
    wrapping at separator boundaries as needed

  Returns the number of lines drawn (for banner height calculation).
  """
  parts = [(k + ':', v) for k, v in active_filters.items() if v != 'All']
  prefix = 'Filters applied — '

  if not parts:
    draw.text((x, y), prefix + 'None', fill=color, font=font_bold)
    return 1

  total_w = _measure_filter_line(draw, parts, font_bold, font_reg, separator)

  if total_w <= max_width:
    # ── Single line ──
    cursor_x = x
    draw.text((cursor_x, y), prefix, fill=color, font=font_bold)
    cursor_x += draw.textlength(prefix, font=font_bold)
    for i, (label, value) in enumerate(parts):
      draw.text((cursor_x, y), label, fill=color, font=font_reg)
      cursor_x += draw.textlength(label, font=font_reg)
      val_str = ' ' + value
      draw.text((cursor_x, y), val_str, fill=color, font=font_reg)
      cursor_x += draw.textlength(val_str, font=font_reg)
      if i < len(parts) - 1:
        draw.text((cursor_x, y), separator, fill=color, font=font_reg)
        cursor_x += draw.textlength(separator, font=font_reg)
    return 1

  else:
    # ── Wrapped: prefix on first line, filters packed onto subsequent lines ──
    line_h    = FILTER_SIZE + LINE_SPACING
    indent    = x   # filters align with left margin, not indented after prefix
    cursor_y  = y
    lines     = 1

    # Draw prefix alone on first line
    draw.text((x, cursor_y), prefix, fill=color, font=font_bold)
    cursor_y += line_h

    # Pack filters onto lines, wrapping at separator boundaries
    cursor_x     = indent
    first_on_line = True

    for i, (label, value) in enumerate(parts):
      part_w = (
        draw.textlength(label, font=font_reg) +
        draw.textlength(' ' + value, font=font_reg)
      )
      sep_w = draw.textlength(separator, font=font_reg) if not first_on_line else 0

      if not first_on_line and cursor_x + sep_w + part_w > max_width:
        # Wrap to next line
        cursor_y     += line_h
        cursor_x      = indent
        first_on_line = True
        sep_w         = 0
        lines        += 1

      if not first_on_line:
        draw.text((cursor_x, cursor_y), separator, fill=color, font=font_reg)
        cursor_x += sep_w

      draw.text((cursor_x, cursor_y), label, fill=color, font=font_reg)
      cursor_x += draw.textlength(label, font=font_reg)
      val_str   = ' ' + value
      draw.text((cursor_x, cursor_y), val_str, fill=color, font=font_reg)
      cursor_x += draw.textlength(val_str, font=font_reg)
      first_on_line = False

    return lines + 1   # +1 for the prefix line


def add_logo_and_filters_pil(img_bytes, active_filters, chart_title='',
                             logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Decorate a raw PNG.

  Top banner (light grey):
    Line 1:   Chart title (large bold)
    Line 2:   Survey-based data downloaded on DATE
    Line 3+:  Filters applied — wraps if too wide

  Chart area:
    White padding surrounds the chart on all sides.

  Bottom strip (white):
    Source citation left, logo right.
  """
  img  = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
  chart_w, chart_h = img.size

  # Canvas width includes horizontal padding
  canvas_w  = chart_w + CHART_PADDING_H * 2
  max_text_w = canvas_w - LEFT_MARGIN - CHART_PADDING_H  # available width for text

  # ── Fonts (needed for measurement before drawing) ──
  font_title    = _load_font(TITLE_TEXT_SIZE,  bold=True)
  font_subtitle = _load_font(SUBTITLE_SIZE,    bold=False)
  font_filter_b = _load_font(FILTER_SIZE,      bold=True)
  font_filter_r = _load_font(FILTER_SIZE,      bold=False)
  font_source   = _load_font(SOURCE_TEXT_SIZE, bold=False)

  # ── Pre-calculate filter line count for banner height ──
  parts        = [(k + ':', v) for k, v in active_filters.items() if v != 'All']
  total_filter_w = _measure_filter_line(
    ImageDraw.Draw(Image.new('RGBA', (1, 1))),
    parts, font_filter_b, font_filter_r, FILTER_SEPARATOR
  ) if parts else 0

  if not parts or total_filter_w <= max_text_w:
    filter_lines = 1
  else:
    # Prefix line + at least one content line
    filter_lines = 2

  line_h_filter = FILTER_SIZE + LINE_SPACING

  # ── Banner height ──
  banner_h = (
    BANNER_TOP_PAD
    + TITLE_TEXT_SIZE  + LINE_SPACING
    + SUBTITLE_SIZE    + LINE_SPACING
    + filter_lines * line_h_filter
    + BANNER_BOTTOM_PAD
  )

  # Chart area height includes vertical padding
  chart_area_h = chart_h + CHART_PADDING_V * 2

  total_h = banner_h + chart_area_h + BOTTOM_STRIP_HEIGHT

  # ── Build canvas ──
  canvas = Image.new('RGBA', (canvas_w, total_h), 'white')
  canvas.paste(Image.new('RGBA', (canvas_w, banner_h), BANNER_BG_COLOR), (0, 0))
  canvas.paste(img, (CHART_PADDING_H, banner_h + CHART_PADDING_V))

  draw = ImageDraw.Draw(canvas)

  # ── Banner: draw lines top-down ──
  cursor_y = BANNER_TOP_PAD

  # Line 1: chart title
  draw.text((LEFT_MARGIN, cursor_y), chart_title, fill=TITLE_TEXT_COLOR, font=font_title)
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

  # Line 3+: filters (wraps automatically)
  _draw_filter_text(
    draw, LEFT_MARGIN, cursor_y,
    active_filters, font_filter_b, font_filter_r,
    FILTER_TEXT_COLOR, FILTER_SEPARATOR, max_text_w
  )

  # ── Bottom strip: source left, logo right ──
  strip_y       = banner_h + chart_area_h
  source_text_y = strip_y + (BOTTOM_STRIP_HEIGHT - SOURCE_TEXT_SIZE) // 2
  draw.text((STRIP_PADDING, source_text_y), SOURCE_TEXT, fill=SOURCE_TEXT_COLOR, font=font_source)

  try:
    logo = _resize_logo(
      Image.open(data_files[logo_filename]).convert('RGBA'),
      LOGO_MAX_HEIGHT, LOGO_MAX_WIDTH
    )
    lw, lh = logo.size
    canvas.paste(
      logo,
      (canvas_w - lw - STRIP_PADDING, strip_y + (BOTTOM_STRIP_HEIGHT - lh) // 2),
      logo
    )
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