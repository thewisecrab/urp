#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METADATA = ROOT / "paper/arxiv/metadata.json"
ALLOWED_FILENAME = re.compile(r"^[A-Za-z0-9_+.,=-]+$")
PROHIBITED_ANNOTATIONS = {"/3D", "/FileAttachment", "/Movie", "/RichMedia", "/Screen", "/Sound"}


def dereference(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def normalize(value: str) -> str:
    return " ".join(value.split())


def markdown_section(document: str, heading: str) -> str:
    marker = f"## {heading}\n"
    if marker not in document:
        return ""
    remainder = document.split(marker, 1)[1]
    return remainder.split("\n## ", 1)[0].strip()


def font_records(reader: PdfReader) -> Iterable[tuple[int, str, Any]]:
    for page_number, page in enumerate(reader.pages, start=1):
        resources = dereference(page.get("/Resources", {}))
        fonts = dereference(resources.get("/Font", {}))
        for resource_name, font_reference in fonts.items():
            font = dereference(font_reference)
            if font.get("/Subtype") == "/Type0":
                descendants = dereference(font.get("/DescendantFonts", []))
                for descendant in descendants:
                    yield page_number, str(resource_name), dereference(descendant)
            else:
                yield page_number, str(resource_name), font


def validate_pdf(reader: PdfReader, pdf_path: Path, metadata: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    if reader.is_encrypted:
        errors.append("PDF must not be encrypted")

    page_count = len(reader.pages)
    comments_match = re.match(r"^(\d+) pages?, (\d+) figures?\.", metadata["comments"])
    if not comments_match:
        errors.append("comments must begin with the page and figure count")
        declared_pages = declared_figures = -1
    else:
        declared_pages, declared_figures = (int(value) for value in comments_match.groups())
        if declared_pages != page_count:
            errors.append(f"comments declare {declared_pages} pages but PDF has {page_count}")

    root = dereference(reader.trailer["/Root"])
    names = dereference(root.get("/Names", {}))
    if "/JavaScript" in names:
        errors.append("PDF contains embedded JavaScript")
    if "/EmbeddedFiles" in names:
        errors.append("PDF contains embedded file attachments")
    open_action = dereference(root.get("/OpenAction", {}))
    if isinstance(open_action, dict) and open_action.get("/S") == "/JavaScript":
        errors.append("PDF has a JavaScript open action")

    page_sizes: set[tuple[float, float]] = set()
    extracted_pages: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        if int(page.get("/Rotate", 0)) % 360:
            errors.append(f"page {page_number} is rotated")
        page_sizes.add((round(float(page.mediabox.width), 1), round(float(page.mediabox.height), 1)))
        extracted_pages.append(page.extract_text() or "")
        for annotation_reference in dereference(page.get("/Annots", [])):
            annotation = dereference(annotation_reference)
            subtype = str(annotation.get("/Subtype", ""))
            if subtype in PROHIBITED_ANNOTATIONS:
                errors.append(f"page {page_number} contains prohibited annotation {subtype}")
            action = dereference(annotation.get("/A", {}))
            if isinstance(action, dict) and action.get("/S") == "/JavaScript":
                errors.append(f"page {page_number} contains a JavaScript action")

    if len(page_sizes) != 1:
        errors.append(f"PDF pages do not use one consistent page size: {sorted(page_sizes)}")
    elif next(iter(page_sizes)) != (595.3, 841.9):
        errors.append(f"PDF must use A4 pages; found {next(iter(page_sizes))}")

    fonts: dict[str, dict[str, Any]] = {}
    for page_number, resource_name, font in font_records(reader):
        subtype = str(font.get("/Subtype", ""))
        base_font = str(font.get("/BaseFont", resource_name))
        record = fonts.setdefault(base_font, {"subtype": subtype, "embedded": True, "pages": set()})
        record["pages"].add(page_number)
        if subtype == "/Type3":
            errors.append(f"bitmap Type 3 font {base_font} is not permitted")
        descriptor = dereference(font.get("/FontDescriptor", {}))
        embedded = isinstance(descriptor, dict) and any(
            key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")
        )
        record["embedded"] = record["embedded"] and embedded
        if not embedded:
            errors.append(f"font {base_font} on page {page_number} is not embedded")

    document_text = "\n".join(extracted_pages)
    required_text = [
        "Universal Reduction Plane",
        "Siddharth Nilesh Patel",
        "Independent Researcher",
        "Abstract",
        "CC BY 4.0",
        "Author declaration and tool disclosure",
        "OpenAI Codex",
        "Appendix B: References",
    ]
    for value in required_text:
        if value not in document_text:
            errors.append(f"machine-readable PDF text is missing: {value}")

    figure_count = len(re.findall(r"Figure\s+\d+\.", document_text))
    if declared_figures >= 0 and figure_count != declared_figures:
        errors.append(f"comments declare {declared_figures} figures but PDF exposes {figure_count} captions")

    pdf_metadata = reader.metadata or {}
    if normalize(str(pdf_metadata.get("/Title", ""))) != metadata["title"]:
        errors.append("PDF title metadata does not match arXiv metadata")
    if str(pdf_metadata.get("/Author", "")) != "Siddharth Nilesh Patel":
        errors.append("PDF author metadata does not match the named author")

    return {
        "bytes": pdf_path.stat().st_size,
        "pages": page_count,
        "page_sizes": sorted(page_sizes),
        "figures": figure_count,
        "fonts": {
            name: {"subtype": value["subtype"], "embedded": value["embedded"], "pages": sorted(value["pages"])}
            for name, value in sorted(fonts.items())
        },
        "text_characters": len(document_text),
        "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
    }


def validate_metadata(metadata: dict[str, Any], errors: list[str]) -> None:
    required = {
        "title",
        "authors",
        "abstract",
        "comments",
        "primary_category",
        "cross_lists",
        "article_license",
        "software_license",
        "source_format",
        "source_document",
        "generator",
        "upload_files",
    }
    missing = sorted(required - metadata.keys())
    if missing:
        errors.append(f"metadata is missing fields: {', '.join(missing)}")
        return

    ascii_fields = [metadata["title"], metadata["abstract"], metadata["comments"], *metadata["authors"]]
    for value in ascii_fields:
        try:
            value.encode("ascii")
        except UnicodeEncodeError:
            errors.append(f"arXiv metadata field is not ASCII: {value[:60]}")

    abstract = normalize(metadata["abstract"])
    if len(abstract) > 1920:
        errors.append(f"abstract has {len(abstract)} characters; arXiv permits at most 1920")
    if abstract.lower().startswith("abstract"):
        errors.append("abstract field must not begin with the word Abstract")
    if metadata["title"].isupper():
        errors.append("title must not use all uppercase letters")
    if metadata["primary_category"] != "cs.DC":
        errors.append("primary category must remain cs.DC for this submission")
    if len(metadata["cross_lists"]) > 2:
        errors.append("arXiv guidance says more than one or two cross-lists is rarely appropriate")
    if len(set(metadata["cross_lists"])) != len(metadata["cross_lists"]):
        errors.append("cross-list categories must be unique")
    if metadata["article_license"] != "CC BY 4.0":
        errors.append("article license must match the selected arXiv CC BY 4.0 license")
    if metadata["software_license"] != "Apache-2.0":
        errors.append("software license must remain distinct from the article license")
    if "ReportLab" not in metadata["source_format"] or "non-TeX" not in metadata["source_format"]:
        errors.append("source format must document that this is an author-generated, non-TeX PDF")
    if len(metadata["upload_files"]) != 1:
        errors.append("PDF submissions must contain exactly one upload file")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the URP PDF and metadata against arXiv submission requirements")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    metadata_path = args.metadata.resolve()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    validate_metadata(metadata, errors)

    upload_files = metadata.get("upload_files") or []
    pdf_details: dict[str, Any] = {}
    if len(upload_files) == 1 and isinstance(upload_files[0], str):
        pdf_path = (ROOT / upload_files[0]).resolve()
        if not ALLOWED_FILENAME.fullmatch(pdf_path.name):
            errors.append(f"upload filename contains characters rejected by arXiv: {pdf_path.name}")
        if not pdf_path.is_file():
            errors.append(f"upload PDF does not exist: {pdf_path}")
        elif "comments" in metadata and "title" in metadata:
            pdf_details = validate_pdf(PdfReader(str(pdf_path)), pdf_path, metadata, errors)

    source_path = (ROOT / metadata.get("source_document", "")).resolve()
    renderer_path = (ROOT / metadata.get("generator", "")).resolve()
    for label, path in (("source document", source_path), ("generator", renderer_path)):
        if not path.is_file():
            errors.append(f"{label} does not exist: {path}")

    bundle = (ROOT / "paper/arxiv/README.md").read_text(encoding="utf-8")
    bundle_abstract = normalize(markdown_section(bundle, "Abstract"))
    if bundle_abstract != normalize(metadata.get("abstract", "")):
        errors.append("README abstract and machine-readable metadata abstract differ")

    public_copy = ROOT / "docs/assets/URP-White-Paper-v1.0.pdf"
    generated_copy = ROOT / "output/pdf/URP-White-Paper-v1.0.pdf"
    if public_copy.is_file() and generated_copy.is_file() and public_copy.read_bytes() != generated_copy.read_bytes():
        errors.append("public and generated PDF copies differ")

    result = {
        "status": "ok" if not errors else "failed",
        "metadata": {
            "abstract_characters": len(normalize(metadata.get("abstract", ""))),
            "authors": metadata.get("authors", []),
            "comments": metadata.get("comments", ""),
            "primary_category": metadata.get("primary_category", ""),
            "cross_lists": metadata.get("cross_lists", []),
        },
        "pdf": pdf_details,
        "errors": errors,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
