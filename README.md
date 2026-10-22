# fastled.io

This repository hosts the static [FastLED website](https://fastled.io/).
Its publishing workflow assembles the website and documentation into a GitHub
Pages deployment. Generated documentation is never committed to Git.

## API documentation

[FastLED/dox](https://github.com/FastLED/dox) builds the documentation from the
exact FastLED release tag. Its standalone site remains available at
https://fastled.github.io/dox/.

This website imports that same generated output under
https://fastled.io/docs/, so matching existing documentation URLs serve their
content directly. Navigation, search, styles, scripts, and images come from the
upstream bundle. The website does not run Doxygen or check out FastLED master.

### Publication and update checks

Dox publishes a small [publication manifest](https://fastled.github.io/dox/publication.json)
with the source release, publication generation, and SHA-256/size of a versioned
GitHub release asset. These downloads outlive the one-day Pages Actions artifact.
`scripts/import_docs.py` verifies the download and its embedded release metadata
before adding the documentation to `_site/docs/`. Import errors fail the workflow
before deployment, leaving the live website intact.

The existing publishing workflow checks daily at **10:47 UTC**. A changed
publication triggers deployment, including an intentional rebuild of the same
release tag. Unchanged documentation checks skip build and deployment. Normal
website pushes still deploy the website with the latest published documentation.
Use **Run workflow → docs_only: true** for an immediate check that deploys only
if documentation changed.

As in dox, `scripts/record_check.py` records a successful check at most every
30 days on `automation/release-checks`. This meaningful audit keeps the scheduled
workflow active during long periods without website edits. Its write permission
is restricted to the audit job and it does not publish the site.

## Local verification

```sh
uv run --no-project python -m unittest discover -s scripts -p 'test_*.py'
```

The importer uses Python 3.12+ and the standard library. A docs import reads the
validated manifest from `PUBLICATION_JSON` and stages into the directory passed
to `python3 scripts/import_docs.py import --site _site`.

## Site migration

The non-documentation site was copied from `FastLED/FastLED`'s former `gh-pages`
branch at `2c2c9e489231912576eed208caeeed1a3392792f`, preserving PaletteKnife's
newer script fixes in this repository. Generated documentation and its history
were excluded. The Pages custom domain remains `fastled.io` with the existing
GitHub Pages DNS records. See
[FastLED/FastLED#4878](https://github.com/FastLED/FastLED/issues/4878) and
[issue #9](https://github.com/FastLED/fastled-fastled.github.io/issues/9).
