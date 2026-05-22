#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile


CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
APP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"


ET.register_namespace("", CT_NS)
ET.register_namespace("", REL_NS)
ET.register_namespace("w", W_NS)
ET.register_namespace("", APP_NS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upgrade DOCX package to modern Word compatibility and help-article defaults."
    )
    parser.add_argument("--input", "-i", required=True, help="Input DOCX file")
    parser.add_argument(
        "--compatibility-mode",
        "-m",
        default="16",
        help="Word compatibility mode value (default: 16)",
    )
    return parser.parse_args()


def add_or_update_content_type(content_types_xml: bytes) -> bytes:
    root = ET.fromstring(content_types_xml)
    overrides = root.findall(f"{{{CT_NS}}}Override")
    existing = {item.attrib.get("PartName", "") for item in overrides}

    needed = {
        "/word/styles.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml",
        "/word/settings.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml",
    }
    for part_name, content_type in needed.items():
        if part_name not in existing:
            ET.SubElement(
                root,
                f"{{{CT_NS}}}Override",
                {"PartName": part_name, "ContentType": content_type},
            )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _next_rel_id(rel_root: ET.Element) -> str:
    ids = []
    for rel in rel_root.findall(f"{{{REL_NS}}}Relationship"):
        rel_id = rel.attrib.get("Id", "")
        m = re.fullmatch(r"rId(\d+)", rel_id)
        if m:
            ids.append(int(m.group(1)))
    return f"rId{(max(ids) if ids else 0) + 1}"


def add_or_update_document_rels(document_rels_xml: bytes) -> bytes:
    root = ET.fromstring(document_rels_xml)
    relationships = root.findall(f"{{{REL_NS}}}Relationship")

    has_styles = False
    has_settings = False
    for rel in relationships:
        rel_type = rel.attrib.get("Type", "")
        target = rel.attrib.get("Target", "")
        if rel_type.endswith("/styles") or target == "styles.xml":
            has_styles = True
        if rel_type.endswith("/settings") or target == "settings.xml":
            has_settings = True

    if not has_styles:
        ET.SubElement(
            root,
            f"{{{REL_NS}}}Relationship",
            {
                "Id": _next_rel_id(root),
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
                "Target": "styles.xml",
            },
        )
    if not has_settings:
        ET.SubElement(
            root,
            f"{{{REL_NS}}}Relationship",
            {
                "Id": _next_rel_id(root),
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings",
                "Target": "settings.xml",
            },
        )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def ensure_styles_xml(styles_xml: bytes | None) -> bytes:
    if styles_xml:
        return styles_xml

    # Minimal modern style set; document-level direct formatting still applies.
    styles = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W_NS}">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
      </w:rPr>
    </w:rPrDefault>
    <w:pPrDefault>
      <w:pPr>
        <w:spacing w:line="300" w:lineRule="auto"/>
      </w:pPr>
    </w:pPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:b/>
      <w:sz w:val="40"/>
      <w:szCs w:val="40"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:qFormat/>
    <w:rPr>
      <w:b/>
      <w:sz w:val="32"/>
      <w:szCs w:val="32"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph">
    <w:name w:val="List Paragraph"/>
    <w:basedOn w:val="Normal"/>
  </w:style>
</w:styles>"""
    return styles.encode("utf-8")


def ensure_settings_xml(settings_xml: bytes | None, compatibility_mode: str) -> bytes:
    if settings_xml:
        root = ET.fromstring(settings_xml)
    else:
        root = ET.Element(f"{{{W_NS}}}settings")

    compat = root.find(f"{{{W_NS}}}compat")
    if compat is None:
        compat = ET.SubElement(root, f"{{{W_NS}}}compat")

    target_setting = None
    for child in compat.findall(f"{{{W_NS}}}compatSetting"):
        if child.attrib.get(f"{{{W_NS}}}name") == "compatibilityMode":
            target_setting = child
            break

    if target_setting is None:
        target_setting = ET.SubElement(compat, f"{{{W_NS}}}compatSetting")

    target_setting.attrib[f"{{{W_NS}}}name"] = "compatibilityMode"
    target_setting.attrib[f"{{{W_NS}}}uri"] = "http://schemas.microsoft.com/office/word"
    target_setting.attrib[f"{{{W_NS}}}val"] = compatibility_mode

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def modernize_document_xml(document_xml: bytes) -> bytes:
    # Normalize fonts used by textutil-generated DOCX to match common Help Center docs.
    text = document_xml.decode("utf-8")
    text = text.replace('w:ascii="Helvetica Neue"', 'w:ascii="Arial"')
    text = text.replace('w:hAnsi="Helvetica Neue"', 'w:hAnsi="Arial"')
    text = text.replace('w:cs="Helvetica Neue"', 'w:cs="Arial"')
    return text.encode("utf-8")


def ensure_app_version(app_xml: bytes | None) -> bytes | None:
    if app_xml is None:
        return None
    root = ET.fromstring(app_xml)
    node = root.find(f"{{{APP_NS}}}AppVersion")
    if node is None:
        node = ET.SubElement(root, f"{{{APP_NS}}}AppVersion")
    node.text = "16.0000"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def modernize_docx(docx_path: Path, compatibility_mode: str) -> None:
    with zipfile.ZipFile(docx_path, "r") as zin:
        files = {name: zin.read(name) for name in zin.namelist()}

    files["[Content_Types].xml"] = add_or_update_content_type(files["[Content_Types].xml"])
    files["word/_rels/document.xml.rels"] = add_or_update_document_rels(
        files["word/_rels/document.xml.rels"]
    )
    files["word/styles.xml"] = ensure_styles_xml(files.get("word/styles.xml"))
    files["word/settings.xml"] = ensure_settings_xml(
        files.get("word/settings.xml"), compatibility_mode
    )
    files["word/document.xml"] = modernize_document_xml(files["word/document.xml"])

    app_xml = ensure_app_version(files.get("docProps/app.xml"))
    if app_xml is not None:
        files["docProps/app.xml"] = app_xml

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for name, data in files.items():
                zout.writestr(name, data)
        os.replace(tmp_path, docx_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    path = Path(args.input)
    if not path.exists():
        raise FileNotFoundError(f"DOCX not found: {path}")
    modernize_docx(path, args.compatibility_mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
