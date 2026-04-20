import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import anvil.media
import base64
import io
from PIL import Image, ImageDraw, ImageFont


def add_logo_and_filters_pil(img_bytes, active_filters, logo_filename='logo.png'):
  """
    Takes a PNG as bytes, stamps filter text and logo using Pillow.
    Returns decorated PNG as bytes.
    """
  # Open the chart image
  img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
  width, height = img.size

  # Add white banner at bottom for filter text
  banner_height = 60
  new_img = Image.new("RGBA", (width, height + banner_height), "white")
  new_img.paste(img, (0, 0))

  draw = ImageDraw.Draw(new_img)

  # Draw filter text in the banner
  filter_parts = [f"{k}: {v}" for k, v in active_filters.items() if v != "All"]
  filter_text = "   |   ".join(filter_parts) if filter_parts else "No filters applied"
  filter_text = "Filters: " + filter_text

  try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
  except:
    font = ImageFont.load_default()

  draw.text((30, height + 15), filter_text, fill="#555555", font=font)

  # Paste logo in top-right corner
  try:
    logo_path = data_files[logo_filename]
    logo = Image.open(logo_path).convert("RGBA")

    # Resize logo to max 60px tall, preserving aspect ratio
    logo_max_height = 60
    ratio = logo_max_height / logo.height
    logo = logo.resize(
      (int(logo.width * ratio), logo_max_height),
      Image.LANCZOS
    )

    # Position: top-right with 10px padding
    x = width - logo.width - 10
    y = 10
    new_img.paste(logo, (x, y), logo)
  except Exception as e:
    print(f"Logo skipped: {e}")

    # Convert back to bytes
  output = io.BytesIO()
  new_img.convert("RGB").save(output, format="PNG")
  return output.getvalue()


def export_figure_from_bytes(img_b64, active_filters, filename="chart_export.png",
                             logo_filename='logo.png'):
  """
    Called from page-specific server callables.
    Accepts base64 PNG string from client, decorates it, returns BlobMedia.
    """
  img_bytes = base64.b64decode(img_b64)
  decorated = add_logo_and_filters_pil(img_bytes, active_filters, logo_filename)
  return anvil.BlobMedia("image/png", decorated, name=filename)
