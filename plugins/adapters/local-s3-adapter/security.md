# Security

- Local-only by default.
- No cross-tenant reuse.
- Object metadata and tags are manifest lineage, not an external index.
- Range reads must use manifest-backed exact rehydration.
- Delete is denied by default and legal hold always blocks tombstoning.
- Multipart completion must verify the final object manifest.
