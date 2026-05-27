from ._anvil_designer import outcomes_impactsTemplate
from anvil import *
import plotly.graph_objects as go
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from .. import config
from ..chart_export import download_chart
# Optional info popup — uncomment once you've created an info form for this page.
from ..InfoPopupOI import InfoPopupOI


class outcomes_impacts(outcomes_impactsTemplate):

  # ==================== INITIALISATION ====================

  def __init__(self, **properties):
    self.init_components(**properties)

    # Prevent filter events firing during setup
    self._initializing   = True
    self._filters_loaded = False

    self._setup_dropdown_formatters()  # before pre-selecting

    # Set default project scale selection
    #self.project_scale_dd.selected = [
     # "Micro (< $100K)", "Small ($100K-$1M)", "Medium ($1M-$5M)",
      #"Large ($5M-$25M)", "Very Large ($25M-$100M)"
   # ]

    self._initializing = False

  def form_show(self, **event_args):
    """Load data once on first show, and highlight the nav link."""
    self.layout.reset_links()
    self._setup_dropdown_formatters()
    self.layout.outcomes_nav.role = 'selected'

    if not self._filters_loaded:
      self._filters_loaded = True
      self.apply_filters()

  # ==================== DROPDOWN SETUP ====================

  def _setup_dropdown_formatters(self):
    """Make every multi-select always show its placeholder, never 'N items selected'."""
    for dd in (
      self.provinces_dd,
      self.proj_types_dd,
      self.stages_dd,
      self.indig_owners_dd,
      self.project_scale_dd,
    ):
      def make_formatter(label):
        def format_selected_text(count, total):
          return label
        return format_selected_text
      dd.format_selected_text = make_formatter(dd.placeholder)

  # ==================== FILTER MANAGEMENT ====================

  def schedule_filter_update(self):
    """Debounce filter changes — waits 1s after the last change before reloading."""
    if getattr(self, '_initializing', False):
      return
    self.filter_timer.interval = 1

  def filter_timer_tick(self, **event_args):
    """Fires after the debounce delay — stops the timer and applies filters."""
    self.filter_timer.interval = 0
    self.apply_filters()

  # Filter change handlers — all route through the debounce timer
  def provinces_dd_change(self, **event_args):
    self.schedule_filter_update()

  def proj_types_dd_change(self, **event_args):
    self.schedule_filter_update()

  def stages_dd_change(self, **event_args):
    self.schedule_filter_update()

  def indig_owners_dd_change(self, **event_args):
    self.schedule_filter_update()

  def project_scale_dd_change(self, **event_args):
    self.schedule_filter_update()

  def remove_filter(self, filter_type, value):
    """Remove a single filter chip value and trigger a refresh."""
    targets = {
      'provinces':            self.provinces_dd,
      'proj_types':           self.proj_types_dd,
      'stages':               self.stages_dd,
      'indigenous_ownership': self.indig_owners_dd,
      'project_scale':        self.project_scale_dd,
    }
    if filter_type in targets:
      current = list(targets[filter_type].selected)
      current.remove(value)
      targets[filter_type].selected = current
    self.schedule_filter_update()

  # ==================== FILTER HELPERS ====================

  def _get_filter_kwargs(self):
    kwargs = {}
    if self.provinces_dd.selected:
      kwargs['provinces'] = self.provinces_dd.selected
    if self.proj_types_dd.selected:
      kwargs['proj_types'] = self.proj_types_dd.selected
    if self.stages_dd.selected:
      kwargs['stages'] = self.stages_dd.selected
    if self.indig_owners_dd.selected:
      INDIG_MAP = {
        'Majority owned (51-100%)': [
          'Wholly Indigenous owned (100%)',
          'Majority Indigenous owned (51-99%)',
        ],
        'Minority owned (1-50%)': [
          'Half Indigenous owned (50%)',
          'Minority Indigenous owned (1-49%)',
        ],
        'No Indigenous ownership': ['No Indigenous ownership'],
      }
      expanded = []
      for selection in self.indig_owners_dd.selected:
        expanded.extend(INDIG_MAP.get(selection, [selection]))
      kwargs['indigenous_ownership'] = expanded
    if self.project_scale_dd.selected:
      kwargs['project_scale'] = self.project_scale_dd.selected
    return kwargs

  def _get_active_filters(self):
    """Returns human-readable filter labels for export annotations."""
    def fmt(selected):
      return ", ".join(selected) if selected else "All"
    return {
      "Provinces":     fmt(self.provinces_dd.selected),
      "Project Types": fmt(self.proj_types_dd.selected),
      "Stages":        fmt(self.stages_dd.selected),
      "Indigenous":    fmt(self.indig_owners_dd.selected),
      "Project Scale": fmt(self.project_scale_dd.selected),
    }

  def _build_filter_chips(self):
    """Build chip data from current filter selections for the repeating panel."""
    chips = []
    mappings = [
      (self.provinces_dd.selected,     'provinces',            'Province'),
      (self.proj_types_dd.selected,    'proj_types',           'Technology'),
      (self.stages_dd.selected,        'stages',               'Stage'),
      (self.indig_owners_dd.selected,  'indigenous_ownership', 'Indigenous Ownership'),
      (self.project_scale_dd.selected, 'project_scale',        'Scale'),
    ]
    for selected, filter_type, label in mappings:
      for value in (selected or []):
        chips.append({'text': f'{label}: {value}', 'tag': (filter_type, value)})
    return chips

  # ==================== CHART LOADING ====================

  def apply_filters(self):
    """Single server call that reloads all charts based on the current filter state."""
    # Update filter chips display
    self.filter_chips_panel.items = self._build_filter_chips()

    # Fetch all charts in one server call
    all_charts = anvil.server.call('get_all_outcomes_charts', **self._get_filter_kwargs())

    # -- Charts --
    self.indigenous_agreements_plot.figure = all_charts['indigenous_agreements']
    self.jobs_plot.figure                  = all_charts['jobs_chart']
    self.ghg_methodology_plot.figure       = all_charts['ghg_methodology']
    self.ghg_timeline_plot.figure          = all_charts['ghg_timeline']
    self.key_objectives_plot.figure        = all_charts['key_objectives']
    self.op_expenses_plot.figure           =all_charts['op_expenses']
    self.return_expectations_plot.figure   =all_charts['return_expectations']
    self.end_use_plot.figure               =all_charts['end_use_composition']

  # ==================== CHART DOWNLOAD ====================

  def _get_plot_component(self, chart_key):
    """Maps a chart key string to the corresponding plot component."""
    return {
      'indigenous_agreements': self.indigenous_agreements_plot,
      'jobs_chart':            self.jobs_plot,
      'ghg_methodology':       self.ghg_methodology_plot,
      'ghg_timeline':          self.ghg_timeline_plot,
      'key_objectives':        self.key_objectives_plot,
      'return_expectations':   self.return_expectations_plot,
      'end_use_composition':   self.end_use_plot
    }[chart_key]

  def _download_chart(self, chart_key, button=None):
    """Capture and download any chart by key. Optionally pass the button for feedback."""
    download_chart(
      plot_component=self._get_plot_component(chart_key),
      chart_key=chart_key,
      active_filters=self._get_active_filters(),
      server_callable='export_outcomes_chart',
      button=button
    )

  # One handler per download button -- wire each to its button in the designer
  def download_indigenous_btn_click(self, **event_args):
    self._download_chart('indigenous_agreements', button=self.download_indigenous_btn)

  def download_jobs_btn_click(self, **event_args):
    self._download_chart('jobs_chart', button=self.download_jobs_btn)

  def download_ghg_methodology_btn_click(self, **event_args):
    self._download_chart('ghg_methodology', button=self.download_ghg_methodology_btn)

  def download_ghg_timeline_btn_click(self, **event_args):
    self._download_chart('ghg_timeline', button=self.download_ghg_timeline_btn)

  def download_key_objectives_btn_click(self, **event_args):
    self._download_chart('key_objectives', button=self.download_key_objectives_btn)

  # ==================== INFO POPUP ====================
  # Optional -- mirrors capital_explorer's info button.
  # Create an info form (e.g. InfoPopupOI), uncomment its import at the top,
  # add an info button in the designer, and wire it to this handler.
  #
  def info_btn_click(self, **event_args):
     alert(
       content=InfoPopupOI(),
       title="How to use this page",
       large=True,
       buttons=[("Close", None)],
     )