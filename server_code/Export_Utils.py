"""
Export_Utils.py — Server-side export utilities
===============================================
Shared by all page server modules. Import and call export_figure_from_bytes()
from any page's export callable.

Usage in a page server module:
    from .Export_Utils import export_figure_from_bytes

    @anvil.server.callable
    def export_my_page_chart(chart_key, img_b64, active_filters):
        return export_figure_from_bytes(
            img_b64,
            active_filters,
            filename=f"{chart_key}_export.png"
        )
"""

import anvil.server
import anvil.media
import base64
import io
from anvil.files import data_files
from PIL import Image, ImageDraw, ImageFont


# ==================== CONFIGURATION ====================

# Filename of the logo in Anvil Assets (case-sensitive)
DEFAULT_LOGO_FILENAME = 'logo.png'

# Height of the white banner added below the chart for filter text
FILTER_BANNER_HEIGHT = 60

# Maximum logo height in pixels (width scales proportionally)
LOGO_MAX_HEIGHT = 300

# Filter text appearance
FILTER_TEXT_COLOR  = "#555555"
FILTER_TEXT_SIZE   = 18
FILTER_TEXT_OFFSET = (30, 15)   # (x, y) position within the banner

# Logo position padding from top-right corner (pixels)
LOGO_PADDING = 10


# ==================== IMAGE DECORATION ====================

def _load_font(size=FILTER_TEXT_SIZE):
  """Load DejaVu Sans if available, fall back to Pillow default."""
  try:
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
  except Exception:
    return ImageFont.load_default()


def _build_filter_text(active_filters):
  """Format the active filters dict into a single annotation string."""
  parts = [f"{k}: {v}" for k, v in active_filters.items() if v != "All"]
  return "Filters: " + ("   |   ".join(parts) if parts else "No filters applied")


def _stamp_filter_text(draw, filter_text, banner_y_start, font):
  """Draw the filter summary text into the white banner."""
  x = FILTER_TEXT_OFFSET[0]
  y = banner_y_start + FILTER_TEXT_OFFSET[1]
  draw.text((x, y), filter_text, fill=FILTER_TEXT_COLOR, font=font)


def _stamp_logo(img, logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Load logo from Anvil Assets, resize it, and paste it into the
  top-right corner of the image. Fails silently if logo not found.
  """
  try:
    logo_path = data_files[logo_filename]
    logo = Image.open(logo_path).convert("RGBA")

    # Resize preserving aspect ratio
    ratio = LOGO_MAX_HEIGHT / logo.height
    logo = logo.resize(
      (int(logo.width * ratio), LOGO_MAX_HEIGHT),
      Image.LANCZOS
    )

    # Position top-right with padding
    x = img.width  - logo.width  - LOGO_PADDING
    y = LOGO_PADDING
    img.paste(logo, (x, y), logo)   # third arg = alpha mask for transparency

  except Exception as e:
    print(f"Logo skipped: {e}")

  return img


def add_logo_and_filters_pil(img_bytes, active_filters, logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Main decoration function. Takes a raw PNG as bytes and returns a
  decorated PNG as bytes with:
    - A white banner at the bottom showing active filter values
    - The app logo stamped in the top-right corner
  """
  # Open original chart image
  img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
  width, height = img.size

  # Create new canvas with extra height for the filter banner
  canvas = Image.new("RGBA", (width, height + FILTER_BANNER_HEIGHT), "white")
  canvas.paste(img, (0, 0))

  # Draw filter text in the banner
  draw       = ImageDraw.Draw(canvas)
  font       = _load_font()
  filter_str = _build_filter_text(active_filters)
  _stamp_filter_text(draw, filter_str, banner_y_start=height, font=font)

  # Stamp logo onto the canvas
  canvas = _stamp_logo(canvas, logo_filename)

  # Convert back to RGB PNG bytes (RGB strips alpha, safe for PNG export)
  output = io.BytesIO()
  canvas.convert("RGB").save(output, format="PNG")
  return output.getvalue()


# ==================== PUBLIC CALLABLE ====================

def export_figure_from_bytes(img_b64, active_filters, filename="chart_export.png",
                             logo_filename=DEFAULT_LOGO_FILENAME):
  """
  Entry point called by every page's export server callable.

  Accepts:
    img_b64:        base64-encoded PNG string captured by the browser
    active_filters: dict of human-readable filter values
    filename:       download filename for the output PNG
    logo_filename:  Anvil Asset filename for the logo (default: logo.png)

  Returns:
    anvil.BlobMedia — ready to pass to anvil.download() on the client
  """
  img_bytes = base64.b64decode(img_b64)
  decorated = add_logo_and_filters_pil(img_bytes, active_filters, logo_filename)
  return anvil.BlobMedia("image/png", decorated, name=filename)