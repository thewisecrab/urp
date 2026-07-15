# URP arXiv Submission Bundle

This directory records the exact metadata for the first arXiv submission of the
Universal Reduction Plane technical paper. The publication PDF is generated from
`docs/WHITE_PAPER.md` and stored at:

- `docs/assets/URP-White-Paper-v1.0.pdf`

Generate it with:

```bash
python3 scripts/render_whitepaper.py
python3 scripts/verify_arxiv_submission.py
```

`metadata.json` is the canonical copy-and-paste source for arXiv's ASCII metadata
fields. The verifier checks that it remains synchronized with this document and the
generated PDF.

## Submission metadata

- Title: `Universal Reduction Plane: A Compatibility-First Control Plane for Reducing Data and AI Waste`
- Author: `Siddharth Nilesh Patel (Independent Researcher)`
- Primary category: `cs.DC` (Distributed, Parallel, and Cluster Computing)
- Suggested cross-lists: `cs.PF` (Performance), `cs.DB` (Databases); use only if both remain directly relevant at submission time
- Comments: `16 pages, 1 figure. Open-source reference implementation and reproducible local evaluation: https://github.com/thewisecrab/urp`
- Report number: leave blank
- Journal reference: leave blank
- DOI: leave blank
- Recommended article license: Creative Commons Attribution 4.0 International (CC BY 4.0)

## Abstract

Modern infrastructure repeatedly pays for the same bytes, data movement, AI
request, prompt context, and derived computation. Existing optimizers usually
make those decisions through different interfaces, policies, verification rules,
and audit records. Universal Reduction Plane (URP) is an open-source,
compatibility-first control and execution plane that gives storage reduction,
exact AI caching, context reduction, routing, and future reducers one lifecycle:
WorkUnit and preservation Contract, Policy, Plan, Execute, Verify, Manifest, and
Ledger. Unknown data defaults to exact bytes, cross-tenant reuse is disabled, and
semantic, approximate, lossy, and deletion paths remain disabled unless explicit
policy and verifier requirements are satisfied. The reference implementation
provides S3-compatible and POSIX object paths, an OpenAI-compatible AI gateway,
typed schemas and SDKs, deployment assets, metrics, manifests, and a hash-chained
ledger. A deterministic local evaluation verifies byte-exact rehydration, range
reads, legal-hold enforcement, same-tenant exact AI cache reuse, redacted evidence,
and ledger integrity without external credentials. We also provide a transparent
impact model that separates measured implementation evidence from workload
assumptions. URP does not claim that every input is reducible; it provides a common,
auditable protocol for accepting avoided work only when the required outcome is
preserved and verified.

## Upload policy

The PDF is produced directly by ReportLab from Markdown rather than from TeX or
LaTeX source. arXiv accepts author-produced PDF submissions but does not accept a
PDF generated from available TeX source in place of that source. Upload exactly
one file, `docs/assets/URP-White-Paper-v1.0.pdf`; do not upload the Markdown source,
repository secrets, build artifacts, or unrelated files.

The paper license and the software license are distinct. The arXiv article can be
distributed under CC BY 4.0 while the implementation remains Apache-2.0.

The generated PDF uses A4 pages, embedded outline TrueType fonts, machine-readable
text, no encryption, no embedded JavaScript, no attachments, and no multimedia.
Its first page identifies the author and affiliation and distinguishes the article
license from the software license.

## Scholarly structure and disclosure

The manuscript is organized as a self-contained systems paper: abstract,
introduction and contributions, problem statement, requirements, architecture,
implementation, threat model, evaluation methodology, results, impact model,
related work, limitations, conclusion, reproducibility formulas, and references.
Measured fixture results, modeled scenarios, and external context are labeled
separately.

The manuscript includes a tool-disclosure section because arXiv asks authors to
report significant use of text-to-text generative AI. OpenAI Codex is identified as
an engineering and language-editing assistant, is not listed as an author, and the
human author explicitly accepts responsibility for the complete work.
