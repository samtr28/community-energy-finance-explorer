from ._anvil_designer import Project_CardTemplate
from anvil import *
import plotly.graph_objects as go
import anvil.server
import m3.components as m3
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables


class Project_Card(Project_CardTemplate):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    self.init_components(**properties)
    self._charts_loaded = False
    self._loading = False

    # Set pill styling
    if self.item.get("data_source") == "Survey response":
      self.data_source_pill.level = "info"
    else: 
      self.data_source_pill.level = "warning"

    # Check if figures are pre-built
    has_ownership = self.item.get("ownership_figure") is not None
    has_capital = self.item.get("capital_mix_figure") is not None

    if has_ownership or has_capital:
      # Figures already built - load when added to page
      self.add_event_handler('x-anvil-page-added', self.on_page_added)
    else:
      # No figures yet - hide plots
      self.ownership_plot.visible = False
      self.capital_mix_plot.visible = False

  def on_page_added(self, **event_args):
    """Load pre-built charts when card is added to page"""
    if not self._charts_loaded and not self._loading:
      self._load_charts()
      self._charts_loaded = True

  def load_figures_if_needed(self, current_filters):
    """
    Public method called when card is clicked via map.
    Loads figures from server if not already loaded.
    """
    # Skip if already loaded or currently loading
    if self._charts_loaded or self._loading:
      print(f"Card {self.item.get('record_id')}: Already loaded or loading")
      return

    # Check if we already have figures (might have been loaded by Load More button)
    if self.item.get("ownership_figure") or self.item.get("capital_mix_figure"):
      print(f"Card {self.item.get('record_id')}: Figures already exist, loading...")
      self._load_charts()
      self._charts_loaded = True
      return

    # Mark as loading to prevent duplicate requests
    self._loading = True

    # Need to fetch figures from server
    record_id = self.item.get('record_id')
    print(f"🔄 On-demand loading figures for card {record_id}...")

    try:
      # Call server to build figures
      figures = anvil.server.call(
        'build_card_figures',
        record_id,
        **current_filters
      )

      if figures:
        print(f"✅ Received figures for card {record_id}")

        # Update item with new figures
        self.item['ownership_figure'] = figures.get('ownership_figure')
        self.item['capital_mix_figure'] = figures.get('capital_mix_figure')

        # Now load them
        self._load_charts()
        self._charts_loaded = True

        print(f"✅ Figures rendered for card {record_id}")
      else:
        print(f"⚠️ No figures returned for card {record_id}")
    except Exception as e:
      print(f"❌ Error loading figures for {record_id}: {e}")
      import traceback
      traceback.print_exc()
    finally:
      self._loading = False

  def _load_charts(self):
    """Assign complete pre-built figures from server"""
    print(f"Loading charts for card {self.item.get('record_id')}...")

    # Ownership plot
    ownership_fig = self.item.get("ownership_figure")
    if ownership_fig:
      try:
        print(f"  - Loading ownership figure...")
        self.ownership_plot.figure = ownership_fig
        self.ownership_plot.config = {"displayModeBar": False}
        self.ownership_plot.visible = True
        print(f"  ✅ Ownership figure loaded")
      except Exception as e:
        print(f"  ❌ Error loading ownership figure: {e}")
        import traceback
        traceback.print_exc()
        self.ownership_plot.visible = False
    else:
      print(f"  - No ownership figure")
      self.ownership_plot.visible = False

    # Capital mix plot
    capital_fig = self.item.get("capital_mix_figure")
    if capital_fig:
      try:
        print(f"  - Loading capital mix figure...")
        self.capital_mix_plot.figure = capital_fig
        self.capital_mix_plot.config = {"displayModeBar": False}
        self.capital_mix_plot.visible = True
        print(f"  ✅ Capital mix figure loaded")
      except Exception as e:
        print(f"  ❌ Error loading capital mix figure: {e}")
        import traceback
        traceback.print_exc()
        self.capital_mix_plot.visible = False
    else:
      print(f"  - No capital mix figure")
      self.capital_mix_plot.visible = False

  def project_card_click(self, **event_args):
    """This method is called when the component is clicked"""
    parent = self.parent  # the RepeatingPanel
    idx = parent.get_components().index(self)
    form = get_open_form()

    # Load figures if clicking on this card
    if hasattr(self, 'load_figures_if_needed'):
      self.load_figures_if_needed(form._current_filters if hasattr(form, '_current_filters') else {})

    # Toggle: if clicking same card, unselect
    if hasattr(form, '_selected_idx') and form._selected_idx == idx:
      form._unselect_all()
    else:
      form._select_index(idx)