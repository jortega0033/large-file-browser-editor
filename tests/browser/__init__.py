"""Browser-side test harness: pages, a harness server and a headless runner.

Nothing here is served by the application and nothing here is collected by
``python -m unittest discover -s tests -t .`` (no file matches ``test*.py``
except the Python tests of the harness itself, which start no browser).
"""
