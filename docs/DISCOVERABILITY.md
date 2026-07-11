# Discoverability and Citation

URP's public documentation is structured for humans, search engines, and answer
engines. Discoverability improves retrieval; it does not guarantee ranking,
indexing, citation, or generated-answer inclusion.

## Implemented surfaces

- one canonical project name and repository URL;
- concise definitions near the start of README and documentation pages;
- descriptive page titles and summaries;
- crawlable static HTML on GitHub Pages;
- canonical URL, Open Graph, and social metadata;
- JSON-LD for `SoftwareSourceCode`, `WebSite`, and the white paper;
- generated `sitemap.xml` and an explicit `robots.txt`;
- a curated `/llms.txt` map for answer-engine retrieval;
- a direct FAQ with self-contained answers;
- `CITATION.cff` and `codemeta.json` for scholarly and software metadata;
- primary-source citations and visible publication dates;
- descriptive internal links rather than ambiguous link text;
- no hidden content, fabricated ratings, or keyword stuffing.

Google recommends JSON-LD as a supported structured-data format, crawlable pages,
and sitemaps, while making clear that structured data does not guarantee a rich
result. See [Google's structured data guidelines](https://developers.google.com/search/docs/appearance/structured-data/sd-policies)
and [sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview).

`llms.txt` is an emerging proposal rather than a search standard. URP uses it as a
curated machine-readable index alongside, not instead of, `robots.txt` and the
sitemap. See the [llms.txt proposal](https://github.com/AnswerDotAI/llms-txt).

## Maintainer checklist

For every public release:

1. Keep README claims aligned with measured evidence.
2. Update white paper publication metadata and references when conclusions change.
3. Regenerate the white paper PDF, package metadata, and release digest.
4. Run the docs build with strict warnings.
5. Validate generated links, canonical URLs, JSON-LD, robots, and sitemap output.
6. Create a tagged GitHub release so citations can identify immutable source.
7. Review GitHub repository description, topics, social preview, and security settings.
8. Avoid changing established terminology without redirects and migration notes.
