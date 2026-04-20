import base64
import copy
import anvil.server
import anvil.media
from anvil.files import data_files
from .Global_Server_Functions import get_data
from .Cap_Explorerr import (
apply_filters,
process_capital_mix_data,
create_sankey_internal,
)


def _load_logo():
  """Read logo.png from Data Files, return a data: URI."""
  try:
    with open(data_files['logo.png'], 'rb') as f:
      b64 = base64.b64encode(f.read()).decode('ascii')
    return f"data:image/png;base64,{b64}"
  except Exception:
    return None


def _build_filter_summary(filters):
  """Turn the filter dict into a readable line for the chart header."""
  labels = {
    'provinces': 'Provinces',
    'proj_types': 'Project types',
    'stages': 'Stages',
    'indigenous_ownership': 'Indigenous ownership',
    'project_scale': 'Project scale',
  }
  parts = []
  for key, label in labels.items():
    val = filters.get(key)
    if val:
      parts.append(f"<b>{label}:</b> {', '.join(val)}")
  if not parts:
    return "<i>No filters applied</i>"
  return "  &nbsp;•&nbsp;  ".join(parts)


def _decorate(fig, title, filter_summary):
  """Add title, filter summary, logo, and bigger margins to a figure copy."""
  fig = copy.deepcopy(fig)
  fig.update_layout(
    width=1600, height=1000,
    paper_bgcolor='white', plot_bgcolor='white',
    margin=dict(l=60, r=60, t=180, b=140),
    title=dict(
      text=(f"<b style='font-size:22px'>{title}</b>"
            f"<br><span style='font-size:13px;color:#555'>{filter_summary}</span>"),
      x=0.02, xanchor='left', y=0.97, yanchor='top',
      font=dict(family='Arial, sans-serif', color='black'),
    ),
  )
  logo = _load_logo()
  if logo:
    existing = list(fig.layout.images) if fig.layout.images else []
    existing.append(dict(
      source=logo, xref='paper', yref='paper',
      x=1.0, y=-0.04, sizex=0.14, sizey=0.14,
      xanchor='right', yanchor='top', layer='above',
    ))
    fig.update_layout(images=existing)
  return fig


@anvil.server.callable
def download_sankey(provinces=None, proj_types=None, stages=None,
                    indigenous_ownership=None, project_scale=None):
  """The ONE callable that the client uses to download the Sankey."""
  filters = {
    'provinces': provinces,
    'proj_types': proj_types,
    'stages': stages,
    'indigenous_ownership': indigenous_ownership,
    'project_scale': project_scale,
  }

  # Build the Sankey exactly like the dashboard does
  df_raw = get_data()
  df_mix = process_capital_mix_data(df_raw)
  df = apply_filters(
    df_mix,
    provinces=provinces,
    proj_types=None,                    # Sankey ignores this filter
    stages=stages,
    indigenous_ownership=indigenous_ownership,
    project_scale=project_scale,
  )
  fig = create_sankey_internal(df, proj_types)

  # Decorate
  fig = _decorate(
    fig,
    title='Capital flow: Source → Category → Project type',
    filter_summary=_build_filter_summary(filters),
  )

  # Export to PNG bytes → BlobMedia
  img_bytes = fig.to_image(format='png', scale=2)
  return anvil.BlobMedia('image/png', img_bytes, name='capital_flow_sankey.png')