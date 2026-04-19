import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "CASTalign"
copyright = "2026, Max Shinn"
author = "Max Shinn"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_parser",
]

autosummary_generate = True
autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_use_param = False

# Optional runtime deps used by GUI/docs imports.
autodoc_mock_imports = [
    "napari",
    "magicgui",
    "vispy",
    "qtpy",
    "PyQt5",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

root_doc = "index"

html_theme = "sphinx_rtd_theme"
html_static_path = ["css", "_static"]
html_css_files = ["extra.css"]
