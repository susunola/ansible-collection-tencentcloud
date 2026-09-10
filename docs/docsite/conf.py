# Sphinx configuration for the susunola.tencentcloud docsite.
#
# The generated module pages under rst/collections/ are produced by
# antsibull-docs (see build.sh); this file only configures the Sphinx build
# around them. `nitpicky` plus `-W` in build.sh is deliberate: an unresolved
# cross-reference such as O(option_that_does_not_exist) fails the build
# instead of shipping a broken link.

project = "Tencent Cloud Collection"
copyright = "Tencent Cloud Ansible Collection Contributors"

title = "Tencent Cloud Collection"
html_short_title = "Tencent Cloud Collection"

extensions = ["sphinx.ext.autodoc", "sphinx.ext.intersphinx", "sphinx_antsibull_ext"]

pygments_style = "ansible"

highlight_language = "YAML+Jinja"

html_theme = "sphinx_ansible_theme"
html_show_sphinx = False

display_version = False

html_use_smartypants = True
html_use_modindex = False
html_use_index = False
html_copy_source = False

# Remote inventories are only consulted when a reference cannot be resolved
# locally; a network outage must not turn into N build errors, so the python
# and jinja2 inventories (never referenced by plugin docs) are dropped and
# only the ansible one is kept.
intersphinx_mapping = {
    "ansible_devel": ("https://docs.ansible.com/projects/ansible/devel/", None),
}

default_role = "any"

nitpicky = True
