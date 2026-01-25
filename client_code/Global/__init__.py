import anvil

# A private variable to cache the value once we've fetched it
_project_explorer_data = None

def __getattr__(name):
    if name == 'project_explorer_data': 
        global _project_explorer_data
        # fetch the value if we haven't loaded it already:
        _project_explorer_data = _project_explorer_data or anvil.server.call('get_all_map_and_cards')
        return _project_explorer_data
    raise AttributeError(name)
    # We must raise an AttributeError at the end of a custom __getattr__
