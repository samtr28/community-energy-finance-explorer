import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import anvil.media
import base64
import plotly.io as pio
import subprocess
import sys
import os

def _ensure_kaleido_chrome():
  try:
    bin_dir = os.path.dirname(sys.executable)
    chrome_script = os.path.join(bin_dir, 'plotly_get_chrome')

    result = subprocess.run(
      [chrome_script],
      input='y\n',          # ← answers the y/n prompt automatically
      capture_output=True,
      text=True,
      timeout=180
    )
    print(f"Return code: {result.returncode}")
    print(f"stdout: {result.stdout}")
    print(f"stderr: {result.stderr}")

  except Exception as e:
    print(f"Chrome install failed: {type(e).__name__}: {e}")

_ensure_kaleido_chrome()

def apply_export_styling(fig):
  """Apply standard export styling to any figure."""
  fig.update_layout(
    plot_bgcolor='white',
    paper_bgcolor='white',
    font=dict(family='Arial, sans-serif', size=13, color='black'),
    margin=dict(l=60, r=60, t=100, b=130),
  )
  return fig


def add_filter_annotation(fig, active_filters):
  """Add filter summary annotation below the chart."""
  filter_parts = [f"<b>{k}:</b> {v}" for k, v in active_filters.items() if v != "All"]
  filter_text = "   |   ".join(filter_parts) if filter_parts else "No filters applied"

  fig.add_annotation(
    text=f"Filters: {filter_text}",
    xref="paper", yref="paper",
    x=0, y=-0.15,
    showarrow=False,
    font=dict(size=10, color="#555555", family="Arial, sans-serif"),
    align="left",
    xanchor="left",
  )
  return fig


def add_logo(fig, logo_filename='logo.png'):
  try:
    # data_files returns a path string, not a media object
    logo_path = data_files[logo_filename]
    with open(logo_path, 'rb') as f:
      logo_bytes = f.read()
    logo_b64 = base64.b64encode(logo_bytes).decode()
    fig.add_layout_image(dict(
      source=f"data:image/png;base64,{logo_b64}",
      xref="paper", yref="paper",
      x=1, y=1.12,
      sizex=0.15, sizey=0.15,
      xanchor="right", yanchor="top",
      layer="above"
    ))
  except Exception as e:
    print(f"Logo skipped: {e}")
  return fig


def export_figure(fig, active_filters, filename="chart_export.png",
                  width=1200, height=700, scale=2, logo_filename='logo.png'):
  """
    Full export pipeline — call this from any page-specific export function.
    Applies styling, adds filters + logo, returns BlobMedia ready for anvil.download().
    """
  fig = apply_export_styling(fig)
  fig = add_filter_annotation(fig, active_filters)
  fig = add_logo(fig, logo_filename)

  img_bytes = pio.to_image(fig, format="png", width=width, height=height, scale=scale)
  return anvil.BlobMedia("image/png", img_bytes, name=filename)
