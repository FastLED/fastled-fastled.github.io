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

## HTTP redirect cutover (pending hosting and DNS access)

`vercel.json` prepares this static site for Vercel. Its `/docs/:path*` rule
returns HTTP 308 to `https://fastled.github.io/dox/:path*`; Vercel forwards the
query string. URL fragments remain client-side. There is no build step and
existing `.html` URLs remain enabled. GitHub Pages continues serving production
until the DNS cutover is verified; its browser redirect remains a fallback.

1. Import `FastLED/fastled-fastled.github.io` into the FastLED Vercel team. Use
   production branch `gh-pages`, root directory `.`, and framework **Other**.
   First deploy the branch containing this configuration as a public preview.
2. Check the preview with `curl -sSI` for `/docs`, `/docs/`,
   `/docs/index.html`, and `/docs/d0/d00/example.html?search=FastLED`.
   Each must return 308 and the corresponding `/dox/` destination, preserving
   the query string. Verify the homepage, `/tools/paletteknife/`, its JavaScript,
   a blog page, images, and CSS still return their expected content. Check a
   missing non-docs path still returns 404.
3. Add `fastled.io` and `www.fastled.io` to the Vercel project, with `www`
   redirecting to the apex. In Gandi, use the exact DNS records and any ownership
   verification records Vercel supplies for this project. Record the existing
   GitHub Pages DNS values first for rollback. Keep unrelated DNS records.
4. After DNS propagation and TLS provisioning, repeat the preview checks against
   `https://fastled.io`, including the redirect status and `Location` header.
   Only then is the HTTP redirect migration complete. Remove the old Pages
   custom-domain binding after the successful cutover. The GitHub Pages preview
   may remain available for rollback.
5. If validation fails, restore the recorded GitHub Pages DNS records and retain
   its custom-domain binding until the incident is resolved.

References: [Vercel redirect behavior](https://vercel.com/docs/routing/redirects),
[project configuration](https://vercel.com/docs/project-configuration/vercel-json),
and [adding domains](https://vercel.com/docs/domains/working-with-domains/add-a-domain).
