# Collection docsite

`antsibull-docs` reads the `DOCUMENTATION` / `RETURN` / `EXAMPLES` blocks of
every module and plugin in `susunola.tencentcloud` and renders them as
`ansible-doc`-style RST; Sphinx turns that into a browsable, searchable HTML
site. It is the same content `ansible-doc` shows, without requiring the
collection to be installed — with 1005 modules that matters, because the
README table is a flat list of names: it links to each module file, but the
options, return values and examples only exist here.

`plugins/event_source` is the one exception. Neither ansible-core nor
antsibull-docs knows that plugin type, so its four plugins would have no page
at all. `scripts/generate_event_source_docs.py` renders one from their
`DOCUMENTATION` / `EXAMPLES` into `extra_rst/`, and `build.sh` copies it in.

## Build

The collection must be importable as `susunola.tencentcloud`, so
`ANSIBLE_COLLECTIONS_PATH` has to point at the directory *containing*
`ansible_collections/`. From a checkout:

```console
$ pip install -r docs/docsite/requirements.txt
$ mkdir -p /tmp/collections/ansible_collections/susunola
$ ln -s "$(pwd)" /tmp/collections/ansible_collections/susunola/tencentcloud
$ ANSIBLE_COLLECTIONS_PATH=/tmp/collections docs/docsite/build.sh
```

Output lands in `docs/docsite/build/html/`; open `index.html` from there.
`docs/docsite/rst/` holds the generated RST: `index.rst` and the pages under
`extra_rst/` are tracked, everything else is regenerated on every build and is
safe to delete.

A cold build takes about five minutes — measured 2026-09-15 at 1,032 pages:
77 s for the antsibull-docs pass and 221 s for Sphinx. It is memory-hungry,
because breadcrumbs build a toctree per plugin. Re-runs are incremental:
rebuilding after one changed page took 43 s.

## What is tracked

| Path | Purpose |
| --- | --- |
| `antsibull-docs.cfg` | antsibull-docs behaviour: breadcrumbs, indexes, collection URLs |
| `conf.py` | Sphinx configuration (theme, `nitpicky`, intersphinx, smart quotes) |
| `build.sh` | the build entry point: antsibull-docs, then the hand-written pages, then Sphinx |
| `requirements.txt` | pinned doc toolchain |
| `rst/index.rst` | the hand-written master document |
| `extra_rst/` | hand-written pages, copied into `rst/` by `build.sh` |
| `build/html/` | the built site, committed on purpose |

Only `/build/doctrees`, `/rst/collections` and the generated top-level
`/rst/*.rst` pages are git-ignored. `build/html/` is tracked so the site can
be read straight from the repository without installing the toolchain; it is
refreshed by hand when plugins change, and no workflow rebuilds it.

## Two flags that are deliberate

`build.sh` passes `--fail-on-error` to `antsibull-docs` and `-W` to
`sphinx-build`.

* `--fail-on-error` makes a module with unparsable documentation **fail** the
  build instead of emitting a page that says "Did not return correct
  DOCUMENTATION". Without it, a broken module ships as a broken page and
  nobody notices.
* `-W` promotes Sphinx warnings to errors, which is what catches
  `O(option_that_does_not_exist)` — a reference to an option that was renamed.

Both were load-bearing when this docsite was added: the first build produced
141 findings across 70 modules, all of them invisible in CI because
`tests/sanity/ignore-2.21.txt` carried 66 blanket
`validate-modules:invalid-documentation` entries. See the roadmap entry for
P1-04.

## Cleanup mode

`build.sh` uses `--cleanup similar-files-and-dirs`, not `--cleanup
everything`. The latter deletes *every* file in the destination directory,
including the tracked `rst/index.rst`, and the Sphinx build then aborts with
"Sphinx is unable to load the master document".

The former is not safe for hand-written pages either: it also removes files
and directories that antsibull-docs did not write, so a page dropped into
`rst/` directly is deleted on the next build. That is why hand-written pages
live in `extra_rst/` and are copied in *after* the antsibull-docs run.

## Sanity tests and the build output

The built HTML is committed, and `ansible-test sanity` checks whatever files
it is given, so the generated pages used to be a problem: Docutils'
smartquotes transform rewrote ASCII quotes into curly ones, and
`no-smart-quotes` failed on the build output whenever sanity ran without a
`.git` to consult — a release tarball, a CI artifact, a plain `rsync`.
`conf.py` now sets `smartquotes = False`, so the generated HTML is pure ASCII
and the run is clean. If smart quotes are ever re-enabled, exclude the
directory:

```console
$ ansible-test sanity --exclude docs/docsite/build --python 3.13 --local
```
