import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables

@anvil.server.callable
def get_pdf_files():
  """Returns a list of PDF files with thumbnails"""
  file_list = []

  for row in app_tables.files.search():
    path = row['path']

    if path.startswith('factsheets/') and not path.endswith('.DS_Store'):
      filename = path.replace('factsheets/', '')

      # Remove .pdf extension for display
      display_name = filename.replace('.pdf', '')

      file_list.append({
        'name': display_name,
        'media': row['file'],
        'thumbnail': row['thumbnail'],
      })

  return file_list