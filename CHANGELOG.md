# Changelog

## v0.1.4

- Rebuild the registry around a cached, site-independent definition catalog for much faster warm loads.
- Add a server-side, permission-protected page/block picker with a 30-result limit and stable definition IDs.
- Make PAGE and nested BLOCK usage counts exact per model, StreamField and definition path.
- Count site root pages correctly and exclude nested subsite trees from per-site results.
- Scan raw StreamField JSON instead of hydrating chooser blocks, eliminating large query cascades during usage filters.
- Group usage scans by page model and fetch only the fields needed for the audit.
- Add exact block usage links, preserve legacy usage URLs, and reduce registry payloads with server-side pagination.
- Add regression tests for stable IDs, nested Timeline/Logo/Image paths, duplicate block instances and site boundaries.

## v0.1.3

- Add on-demand registry filters for component type, site and total usage ranges.
- Make unused pages and blocks discoverable without loading usage counts on the initial registry view.
- Improve nested block discovery with full hierarchy paths and label fallbacks.
- Add a compact, searchable page and block chooser with distinct PAGE and BLOCK badges.
- Improve usage-detail search, sorting and copy the displayed table to the clipboard.
- Test compatibility with Wagtail 7.4.2 LTS.
