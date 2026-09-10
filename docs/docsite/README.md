# Collection docsite

`antsibull-docs` reads the `DOCUMENTATION` / `RETURN` / `EXAMPLES` blocks of
every module and plugin in `susunola.tencentcloud` and renders them as
`ansible-doc`-style RST; Sphinx turns that into a browsable, searchable HTML
site. It is the same content `ansible-doc` shows, without requiring the
collection to be installed — which matters for a collection with ~875 modules,
because the only index of them today is the README table.

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
`docs/docsite/rst/` holds the generated RST (git-ignored apart from
`index.rst`) and is safe to delete — the next build recreates it.

A full build takes about eight minutes for 875 modules (3-4 min for the RST
generation, 4-5 min for Sphinx) and needs roughly 2 GB of memory because
breadcrumbs build a toctree per plugin.

## What is tracked

| Path | Purpose |
| --- | --- |
| `antsibull-docs.cfg` | antsibull-docs behaviour: breadcrumbs, indexes, collection URLs |
| `conf.py` | Sphinx configuration (theme, `nitpicky`, intersphinx) |
| `build.sh` | the two-step build entry point |
| `requirements.txt` | pinned doc toolchain |
| `rst/index.rst` | the hand-written master document |

Everything else under `rst/` and `build/` is generated and ignored.

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

## Sanity tests and the build output

`docs/docsite/build/` is git-ignored, and `ansible-test sanity` honours
`.gitignore`, so a build tree never affects the sanity run in a checkout. It
*does* matter when the collection is copied somewhere without `.git` (a
release tarball, a CI artifact, a plain `rsync`): without git to consult,
sanity scans everything on disk, and `no-smart-quotes` then flags the 38
typographic quotes Sphinx emits in the generated HTML. Exclude the directory
in that case:

```console
$ ansible-test sanity --exclude docs/docsite/build --python 3.13 --local
```
