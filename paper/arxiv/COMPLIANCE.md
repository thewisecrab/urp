# arXiv Compliance Record

Last reviewed against official arXiv guidance: 2026-07-15.

This record explains why the URP submission bundle is prepared as it is. It is a
release checklist, not a guarantee of moderator acceptance. arXiv retains
discretion to reclassify or decline a submission.

## Scholarly content

- The manuscript is self-contained and uses a neutral technical tone.
- It states a systems research question and four explicit contributions.
- Architecture, implementation, threat model, methodology, results, related work,
  limitations, conclusion, and references are separate sections.
- Local measurements, modeled scenarios, and external context are distinguished.
- The author-maintained nature of the implementation and the absence of independent
  reproduction are disclosed.
- Significant use of OpenAI Codex is disclosed; the tool is not an author, and the
  human author accepts responsibility for the work.

Official guidance:

- [Submission Guidelines](https://info.arxiv.org/help/submit/index.html)
- [Content Moderation](https://info.arxiv.org/help/moderation/index.html)

## Identity and metadata

- Title, author, affiliation, abstract, comments, category, and license are stored
  in `metadata.json`.
- All arXiv form fields are ASCII.
- The abstract is no more than 1,920 characters and does not start with the word
  `Abstract`.
- Comments begin with the verified page and figure count.
- Report number, journal reference, and DOI remain blank because none is applicable.

Official guidance:

- [Metadata for Required and Optional Fields](https://info.arxiv.org/help/prep.html)

## Category selection

- Primary category: `cs.DC`, because the work is a control plane for distributed
  storage, cluster, and AI-serving infrastructure with fault-aware fallback and
  service-level verification.
- Suggested cross-lists: `cs.PF` for measurement and evaluation, and `cs.DB` for
  object, manifest, deduplication, and data-processing paths.
- Use no more than those two cross-lists, and remove either if it is no longer of
  direct interest to that category at submission time.

Official guidance:

- [Category Taxonomy](https://arxiv.org/category_taxonomy)
- [Category Cross Listing](https://info.arxiv.org/help/cross.html)

## PDF upload

- Upload exactly one file: `docs/assets/URP-White-Paper-v1.0.pdf`.
- The PDF is generated directly from Markdown with ReportLab; no TeX or LaTeX source
  exists for the article.
- All fonts are embedded outline TrueType fonts; no Type 3 fonts are used.
- The PDF is machine readable, unencrypted, A4, and free of JavaScript, embedded
  attachments, multimedia, and rotated pages.
- The upload filename uses only arXiv-safe characters.

Official guidance:

- [Submit a PDF](https://info.arxiv.org/help/submit_pdf.html)

## Rights and licenses

- The article is licensed under CC BY 4.0, matching the arXiv selection.
- The reference implementation remains Apache-2.0; the first page distinguishes the
  article and software licenses.
- The human author certifies the right to submit the manuscript and grant the
  selected article license.

Official guidance:

- [arXiv License Information](https://info.arxiv.org/help/license/index.html)

## Automated verification

Run:

```bash
python3 scripts/render_whitepaper.py
python3 scripts/verify_arxiv_submission.py --report output/arxiv-compliance.json
```

The verifier fails on metadata drift, excessive abstract length, non-ASCII form
text, mismatched page or figure counts, missing disclosure text, unembedded or Type
3 fonts, encryption, JavaScript, attachments, multimedia, inconsistent page sizes,
or differences between the generated and public PDF copies.

## Final submission gate

Before selecting `Submit Article`, inspect arXiv's processed preview and confirm
that its title, author, abstract, comments, category, cross-lists, license, page
count, figure, links, and text extraction match this bundle. Endorsement is an
external arXiv account state: if submission `7829636` still shows a `cs.DC`
endorsement gate, an eligible endorser must approve it before file upload.
