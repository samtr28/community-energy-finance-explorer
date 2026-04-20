import anvil.server, anvil.media
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
# client_code/download_helper.py


# Keep this list in sync with FILTERS on the server (or fetch it once on startup)
FILTER_TO_COMPONENT = {
  'provinces':            'provinces_dd',
  'proj_types':           'proj_types_dd',
  'stages':               'stages_dd',
  'indigenous_ownership': 'indig_owners_dd',
  'project_scale':        'project_scale_dd',
}

def download_chart(form, chart_id, fmt='png'):
  kwargs = {}
  for filter_name, attr_name in FILTER_TO_COMPONENT.items():
    component = getattr(form, attr_name, None)
    if component is not None and component.selected:
      kwargs[filter_name] = component.selected
  media = anvil.server.call('download_chart', chart_id, fmt=fmt, **kwargs)
  anvil.media.download(media)
