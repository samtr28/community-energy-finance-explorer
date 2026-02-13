import anvil.server
import anvil.tables as tables
import anvil.tables.query as q
from anvil.tables import app_tables
from anvil.js.window import jQuery as _S
import anvil.js as js
from anvil import *

class AutoScroll:
  def __init__(self, loader_function, *,
               scrollbar_load_threshold=400, start_loading=True, debugging=True):
    self.loader_function = loader_function
    self.scrollbar_load_threshold = scrollbar_load_threshold
    self.start_loading = start_loading
    self.debugging = debugging
    self.loading = False

    # Target the scrollable elements
    self.jq_elements_with_scrollbar = _S('.anvil-container', 'body')
    self.jq_elements_with_scrollbar.on('scroll', self.on_scroll)

    if self.start_loading:
      self._print('Start initial automatic load')
      self.jq_elements_with_scrollbar.trigger('scroll')
      self._print('End initial automatic load')

  def on_scroll(self, *args):
    self._print(f'============== scroll detected ==============')
    if self.loading:
      self._print('Already loading... skipping')
      return

    scroll_top = self.max_scroll_top(self.jq_elements_with_scrollbar)
    height = self.min_height(self.jq_elements_with_scrollbar)
    scroll_height = self.max_scroll_height(self.jq_elements_with_scrollbar)

    self._print(f'scroll_top:{scroll_top}  height:{height}  scroll_height:{scroll_height}')

    # Check if near bottom
    if scroll_height - scroll_top - height < self.scrollbar_load_threshold:
      self._print(f'Near bottom, triggering load')
      self.loading = True
      try:
        more_available = self.loader_function()
        if more_available and self.start_loading:
          self._print('More data available, checking scroll again')
          self.jq_elements_with_scrollbar.trigger('scroll')
      finally:
        self.loading = False
    else:
      self._print(f'Not near bottom yet')

  def _print(self, text):
    if self.debugging:
      print(text)

  def max_scroll_top(self, jq_object):
    return max(jq_object.slice(n).scrollTop() for n in range(len(jq_object)))

  def min_height(self, jq_object):
    return min(jq_object.slice(n).height() for n in range(len(jq_object)))

  def max_scroll_height(self, jq_object):
    return max(jq_object.slice(n).get(0).scrollHeight for n in range(len(jq_object)))