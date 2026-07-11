# URP Local Plugin Packages

This directory contains conformance-ready local plugin package scaffolds for the
core URP extension points. They are intentionally small: default local tests use
the Python reference runtime, while these packages pin the descriptor, package
shape, security notes, and examples that a real plugin must preserve.

Each package includes `plugin.yaml`, `plugin.json`, `README.md`, `security.md`,
`src/`, `tests/`, `conformance/`, and `examples/`.
