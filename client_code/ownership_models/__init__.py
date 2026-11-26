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
from ..CategoryPopup import CategoryPopup
from ..filter_bar import build_filter_bar


class ownership_models(ownership_modelsTemplate):

  # ==================== INITIALISATION ====================

  def __init__(self, **properties):
    self.init_components(**properties)

    self._filters_loaded = False
    self._load_id = 0

    self.filters = build_filter_bar(
      self.filter_bar,
      on_apply=self.apply_filters,
      defaults={'project_scale': [
        "Micro (< $100K)", "Small ($100K-$1M)", "Medium ($1M-$5M)",
        "Large ($5M-$25M)", "Very Large ($25M-$100M)"
      ]},
    )

  def form_show(self, **event_args):
    self.layout.reset_links()
    self.layout.ownership_nav.role = 'selected'
    if not self._filters_loaded:
      self._filters_loaded = True
      self.apply_filters()

  # ==================== FILTER HELPERS ====================

  def _get_filter_kwargs(self):
    return self.filters.get_kwargs()

  def _get_active_filters(self):
    """Human-readable filter labels for export annotations."""
    return self.filters.get_active_labels()

  # ==================== CHART LOADING ====================

  def apply_filters(self):
    self._load_id += 1
    load_id = self._load_id

    self.filters.refresh_ui()
    self.filters.show_loading()

    all_charts = anvil.server.call('get_all_ownership_charts', **self._get_filter_kwargs())
    if load_id != self._load_id:
      return                       # a newer change started while this one loaded
    self.filters.show_count(all_charts)

    self.ownership_treemap.figure          = all_charts['ownership_treemap']
    self.scale_pies_plot.figure            = all_charts['scale_pies']
    #self.indig_ownership_plot.figure       = all_charts['indigenous_pie']
    #self.lollipop_chart.figure              = all_charts['bottleneck_chart']   # now governance bottlenecks
    # self.ownership_financing_bubble.figure = all_charts['bubble_chart']    # REMOVED
    self.all_financing_heatmap_plot.figure  = all_charts['all_financing_heatmap']
    #self.ownership_boxplot_plot.figure      = all_charts['ownership_boxplot']
    self.ownership_tiers_histogram.figure   = all_charts['ownership_tiers_histogram']
    #self.collaboration_heatmap_plot.figure  = all_charts['collaboration_heatmap']    # NEW
    self.single_owner_breakdown_plot.figure = all_charts['single_owner_breakdown']   # NEW
    self.semicircles_plot.figure = all_charts['multi_owner_semicircles']
    self.objectives_heatmap_plot.figure = all_charts['objectives_heatmap']

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
      #'collaboration_heatmap':     self.collaboration_heatmap_plot,    # NEW
      'single_owner_breakdown':    self.single_owner_breakdown_plot,   # NEW
      'multi_owner_semicircles': self.semicircles_plot,
      'objectives_heatmap':        self.objectives_heatmap_plot,
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

  def category_button_click(self, **event_args):
    alert(
      content=CategoryPopup(),
      title="Ownership Categories",
      dismissible=True,
      large=True
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