"""Fixed public shell/assets only. Diagnostic data still needs the API token."""
from pathlib import Path

ASSETS = {'/panel': ('panel.html', 'text/html'),
          '/panel.css': ('panel.css', 'text/css'),
          '/panel.js': ('panel.js', 'text/javascript'),
          '/app': ('app.html', 'text/html'),
          '/app.css': ('app.css', 'text/css'),
          '/app.js': ('app.js', 'text/javascript')}


def panel_asset(route):
    filename, media_type = ASSETS[route]
    return (Path(__file__).with_name('web') / filename).read_text(encoding='utf-8'), media_type
