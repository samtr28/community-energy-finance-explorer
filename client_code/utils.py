import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
# This is a module.
# You can define variables and functions here, and use them from any form. For example, in a top-level form:

def get_active_filters(form):
  active_filters = {}
  if form.provinces_dd.selected:
    active_filters['provinces'] = list(form.provinces_dd.selected)
  if form.proj_types_dd.selected:
    active_filters['proj_types'] = list(form.proj_types_dd.selected)
  if form.stages_dd.selected:
    active_filters['stages'] = list(form.stages_dd.selected)
  if form.indig_owners_dd.selected:
    active_filters['indigenous_ownership'] = list(form.indig_owners_dd.selected)
  if form.project_scale_dd.selected:
    active_filters['project_scale'] = list(form.project_scale_dd.selected)
  return active_filters


def download_chart(form, plot_component, filename):
  media = anvil.server.call(
    'download_chart',
    plot_component.figure,
    get_active_filters(form),
    filename
  )
  anvil.media.download(media)