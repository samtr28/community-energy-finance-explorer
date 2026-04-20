import anvil.files
from anvil.files import data_files
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
import anvil.server
import base64, copy
import anvil.server, anvil.media
from anvil.files import data_files

# ---------- The global filter schema (declared once) ----------
FILTERS = [
  ('provinces',            'Provinces'),
  ('proj_types',           'Project types'),
  ('stages',               'Stages'),
  ('indigenous_ownership', 'Indigenous ownership'),
  ('project_scale',        'Project scale'),
]
FILTER_NAMES = [name for name, _ in FILTERS]

# ---------- Registries ----------
DATA_SOURCES = {}
CHART_REGISTRY = {}

def register_data_source(name):
  def decorator(fn):
    DATA_SOURCES[name] = fn
    return fn
  return decorator

def register_chart(chart_id, *, title, filename, data_source, builder):
  CHART_REGISTRY[chart_id] = {
    'title': title,
    'filename': filename,
    'data_source': data_source,
    'builder': builder,
  }

# ---------- Decoration helpers ----------
def _load_logo_datauri(filename='logo.png'):
  try:
    with open(data_files[filename], 'rb') as f:
      return f"data:image/png;base64,{base64.b64encode(f.read()).decode('ascii')}"
  except Exception:
    return None

def build_filter_summary(filters):
  parts = []
  for key, label in FILTERS:
    val = filters.get(key)
    if val:
      parts.append(f"<b>{label}:</b> {', '.join(val)}")
  if not parts:
    return "<i>No filters applied — all projects included</i>"
  return "  &nbsp;•&nbsp;  ".join(parts)

def decorate_for_download(fig, chart_title, filter_summary,
                          width=1600, height=1000, logo_filename='logo.png'):
  fig = copy.deepcopy(fig)
  fig.update_layout(
    width=width, height=height,
    paper_bgcolor='white', plot_bgcolor='white',
    margin=dict(l=60, r=60, t=180, b=140),
    title=dict(
      text=(f"<b style='font-size:22px'>{chart_title}</b>"
            f"<br><span style='font-size:13px;color:#555'>{filter_summary}</span>"),
      x=0.02, xanchor='left', y=0.97, yanchor='top',
      font=dict(family='Arial, sans-serif', color='black'),
    ),
  )
  fig.add_annotation(
    text="<i>Capital Explorer — generated with the filters shown above</i>",
    xref='paper', yref='paper', x=0.0, y=-0.11,
    xanchor='left', yanchor='top', showarrow=False,
    font=dict(size=11, color='#777', family='Arial, sans-serif'),
  )
  logo_src = _load_logo_datauri(logo_filename)
  if logo_src:
    existing = list(fig.layout.images) if fig.layout.images else []
    existing.append(dict(
      source=logo_src, xref='paper', yref='paper',
      x=1.0, y=-0.04, sizex=0.14, sizey=0.14,
      xanchor='right', yanchor='top', layer='above',
    ))
    fig.update_layout(images=existing)
  return fig

def figure_to_media(fig, filename_base, fmt='png', scale=2):
  img_bytes = fig.to_image(format=fmt, scale=scale)
  mime = {'png':'image/png','jpeg':'image/jpeg','svg':'image/svg+xml','pdf':'application/pdf'}
  return anvil.BlobMedia(mime.get(fmt, 'application/octet-stream'),
                         img_bytes, name=f"{filename_base}.{fmt}")

# ---------- The single download endpoint ----------
@anvil.server.callable
def download_chart(chart_id, fmt='png', **filters):
  if chart_id not in CHART_REGISTRY:
    raise ValueError(f"Unknown chart: {chart_id}")
  cfg = CHART_REGISTRY[chart_id]
  df = DATA_SOURCES[cfg['data_source']](filters)
  fig = cfg['builder'](df, filters)
  fig = decorate_for_download(fig, cfg['title'], build_filter_summary(filters))
  return figure_to_media(fig, filename_base=cfg['filename'], fmt=fmt)
