from ._anvil_designer import ownership_modelsTemplate
from anvil import *
import plotly.graph_objects as go
import m3.components as m3
import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from .. import config
from ..chart_export import download_chart
from ..InfoPopupOM import InfoPopupOM


class ownership_models(ownership_modelsTemplate):

  # ==================== INITIALISATION ====================

  def __init__(self, **properties):
    self.init_components(**properties)
    self._initializing   = True
    self._filters_loaded = False
    self._setup_dropdown_formatters()

    self._initializing = False

  def form_show(self, **event_args):
    self.layout.reset_links()
    self.layout.ownership_nav.role = 'selected'
    if not self._filters_loaded:
      self._filters_loaded = True
      self.apply_filters()

  # ==================== DROPDOWN SETUP ====================

  def _setup_dropdown_formatters(self):
    for dd in (
      self.provinces_dd, self.proj_types_dd, self.stages_dd,
      self.indig_owners_dd, self.project_scale_dd,
    ):
      def make_formatter(label):
        def format_selected_text(count, total):
          return label
        return format_selected_text
      dd.format_selected_text = make_formatter(dd.placeholder)

  # ==================== FILTER MANAGEMENT ====================

  def schedule_filter_update(self):
    if getattr(self, '_initializing', False):
      return
    self.filter_timer.interval = 1

  def filter_timer_tick(self, **event_args):
    self.filter_timer.interval = 0
    self.apply_filters()

  def provinces_dd_change(self,     **event_args): self.schedule_filter_update()
  def proj_types_dd_change(self,    **event_args): self.schedule_filter_update()
  def stages_dd_change(self,         **event_args): self.schedule_filter_update()
  def indig_owners_dd_change(self,  **event_args): self.schedule_filter_update()
  def project_scale_dd_change(self, **event_args): self.schedule_filter_update()

  def remove_filter(self, filter_type, value):
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
    if self.provinces_dd.selected:     kwargs['provinces']   = self.provinces_dd.selected
    if self.proj_types_dd.selected:    kwargs['proj_types']  = self.proj_types_dd.selected
    if self.stages_dd.selected:        kwargs['stages']      = self.stages_dd.selected
    if self.indig_owners_dd.selected:
      INDIG_MAP = {
        'Majority owned (51-100%)': ['Wholly Indigenous owned (100%)', 'Majority Indigenous owned (51-99%)'],
        'Minority owned (1-50%)':   ['Half Indigenous owned (50%)',    'Minority Indigenous owned (1-49%)'],
        'No Indigenous ownership':  ['No Indigenous ownership'],
      }
      expanded = []
      for s in self.indig_owners_dd.selected:
        expanded.extend(INDIG_MAP.get(s, [s]))
      kwargs['indigenous_ownership'] = expanded
    if self.project_scale_dd.selected: kwargs['project_scale'] = self.project_scale_dd.selected
    return kwargs

  def _get_active_filters(self):
    def fmt(sel): return ", ".join(sel) if sel else "All"
    return {
      "Provinces":     fmt(self.provinces_dd.selected),
      "Project Types": fmt(self.proj_types_dd.selected),
      "Stages":        fmt(self.stages_dd.selected),
      "Indigenous":    fmt(self.indig_owners_dd.selected),
      "Project Scale": fmt(self.project_scale_dd.selected),
    }

  def _build_filter_chips(self):
    chips = []
    mappings = [
      (self.provinces_dd.selected,     'provinces',           'Province'),
      (self.proj_types_dd.selected,    'proj_types',          'Project Type'),
      (self.stages_dd.selected,        'stages',              'Stage'),
      (self.indig_owners_dd.selected,  'indigenous_ownership','Indigenous'),
      (self.project_scale_dd.selected, 'project_scale',       'Scale'),
    ]
    for selected, filter_type, label in mappings:
      for value in (selected or []):
        chips.append({'text': f'{label}: {value}', 'tag': (filter_type, value)})
    return chips

  # ==================== CHART LOADING ====================

  def apply_filters(self):
    self.filter_chips_panel.items = self._build_filter_chips()
    #self.selected_panel.visible   = len(self.filter_chips_panel.items) > 0

    all_charts = anvil.server.call('get_all_ownership_charts', **self._get_filter_kwargs())

    self.ownership_treemap.figure          = all_charts['ownership_treemap']
    self.scale_pies_plot.figure            = all_charts['scale_pies']
    #self.indig_ownership_plot.figure       = all_charts['indigenous_pie']
    self.lollipop_chart.figure              = all_charts['bottleneck_chart']   # now governance bottlenecks
    # self.ownership_financing_bubble.figure = all_charts['bubble_chart']    # REMOVED
    self.all_financing_heatmap_plot.figure  = all_charts['all_financing_heatmap']
    #self.ownership_boxplot_plot.figure      = all_charts['ownership_boxplot']
    self.ownership_tiers_histogram.figure   = all_charts['ownership_tiers_histogram']
    self.collaboration_heatmap_plot.figure  = all_charts['collaboration_heatmap']    # NEW
    self.single_owner_breakdown_plot.figure = all_charts['single_owner_breakdown']   # NEW
    self.semicircles_plot.figure = all_charts['multi_owner_semicircles']
  # ==================== CHART DOWNLOAD ====================

  def _get_plot_component(self, chart_key):
    return {
      'ownership_treemap':         self.ownership_treemap,
      'scale_pies':                self.scale_pies_plot,
      #'indigenous_pie':            self.indig_ownership_plot,
      'bottleneck_chart':            self.lollipop_chart,
      'all_financing_heatmap':     self.all_financing_heatmap_plot,
      #'ownership_boxplot':         self.ownership_boxplot_plot,
      'ownership_tiers_histogram': self.ownership_tiers_histogram,
      'collaboration_heatmap':     self.collaboration_heatmap_plot,    # NEW
      'single_owner_breakdown':    self.single_owner_breakdown_plot,   # NEW
      'multi_owner_semicircles': self.semicircles_plot,
    }[chart_key]

  def _download_chart(self, chart_key, button=None):
    download_chart(
      plot_component=self._get_plot_component(chart_key),
      chart_key=chart_key,
      active_filters=self._get_active_filters(),
      server_callable='export_ownership_chart',
      button=button,
    )

  def info_btn_click(self, **event_args):
    alert(
      content=InfoPopupOM(),
      title="How to use this page",
      large=True,
      buttons=[("Close", None)],
    )

  # ── Download button handlers (uncomment when buttons added in the designer) ──
  #
  # def download_treemap_btn_click(self, **event_args):
  #   self._download_chart('ownership_treemap', button=self.download_treemap_btn)
  #
  # def download_pies_btn_click(self, **event_args):
  #   self._download_chart('scale_pies', button=self.download_pies_btn)
  #
  # def download_indigenous_btn_click(self, **event_args):
  #   self._download_chart('indigenous_pie', button=self.download_indigenous_btn)
  #
  # def download_bottleneck_btn_click(self, **event_args):
  #   self._download_chart('lollipop_chart', button=self.download_bottleneck_btn)
  #
  # def download_bubble_btn_click(self, **event_args):
  #   self._download_chart('bubble_chart', button=self.download_bubble_btn)
  #
  # def download_heatmap_btn_click(self, **event_args):
  #   self._download_chart('heatmap', button=self.download_heatmap_btn)
  #
  # def download_all_financing_btn_click(self, **event_args):
  #   self._download_chart('all_financing_heatmap', button=self.download_all_financing_btn)

  # def download_boxplot_btn_click(self, **event_args):
  #   self._download_chart('ownership_boxplot', button=self.download_boxplot_btn)

    # def download_histogram_btn_click(self, **event_args):
  #   self._download_chart('ownership_tiers_histogram', button=self.download_boxplot_btn)

  # def download_semicircles_btn_click(self, **event_args):
  #   self._download_chart('multi_owner_semicircles', button=self.download_semicircles_btn)