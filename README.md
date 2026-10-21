# fastled.io

This repository hosts the static [FastLED website](https://fastled.io/).
Its deployment workflow uploads the tracked site files directly to GitHub Pages.

## API documentation

The API reference is published separately at https://fastled.github.io/dox/ by
[FastLED/dox](https://github.com/FastLED/dox), which checks daily for a new stable
FastLED release. This repository contains no generated Doxygen reference.

The homepage links directly to the new reference. `/docs/` redirects there;
the custom 404 page redirects old `/docs/...` deep links to corresponding pages,
preserving their query parameters and fragments. GitHub Pages serves those deep
redirects with HTTP 404; browsers follow the JavaScript redirect.

## Site migration

The non-documentation site was copied from `FastLED/FastLED`'s former `gh-pages`
branch at `2c2c9e489231912576eed208caeeed1a3392792f`, preserving PaletteKnife's
newer script fixes in this repository. Generated documentation and its history
were excluded. The Pages custom domain is `fastled.io`; DNS remains on GitHub
Pages. Migration history is tracked in
[FastLED/FastLED#4878](https://github.com/FastLED/FastLED/issues/4878).
