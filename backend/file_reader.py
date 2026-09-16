"""Universal file content extraction for uploaded documents.

Supports PDF, DOCX, XLSX, XLS, PPTX, ODT/ODS/ODP, EPUB, CSV/TSV, RTF and a
wide range of plain-text formats (TXT/MD/JSON/HTML/XML/YAML/LOG and code
files). Images are handled by the vision/OCR service elsewhere. Every branch
is defensive: a file that cannot be read returns a safe placeholder instead
of raising, so commit/indexing never fails on an unusual format.
"""
import csv
import io
import logging
import zipfile
from typing import Optional
from xml.etree import ElementTree as ET

logger = logging.getLogger("ai_os.file_reader")

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".json", ".jsonl", ".html", ".htm",
    ".xml", ".yaml", ".yml", ".log", ".ini", ".cfg", ".conf",
    ".py", ".js", ".ts", ".tsx", ".sql", ".sh", ".css", ".env",
    ".csv", ".tsv", ".eml", ".mbox",
    ".geojson", ".topojson",
}

BINARY_HINT = "[Binary or unsupported file"


def _decode_text(data: bytes) -> str:
    for enc in ("utf-8", "utf-16", "latin-1", "cp1252"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def _looks_like_text(data: bytes) -> bool:
    sample = data[:4096]
    if not sample:
        return True
    printable = sum(1 for c in sample if c in (9, 10, 13) or 32 <= c < 127 or c > 160)
    return printable / len(sample) > 0.85


def _extract_html(data: bytes) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "noscript", "head", "svg"]):
        tag.decompose()
    return soup.get_text("\n")


def _extract_opendocument(data: bytes) -> str:
    """Extract text from ODF (ODT/ODS/ODP) zip containers via content.xml."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        root = ET.fromstring(zf.read("content.xml"))
    parts = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "p":
            txt = "".join(node.itertext()).strip()
            if txt:
                parts.append(txt)
        elif tag == "cell":
            txt = "".join(node.itertext()).strip()
            if txt:
                parts.append(" | " + txt)
    return "\n".join(parts)


def _rtf_to_text(rtf: str) -> str:
    """Decode the essential text out of RTF control words (best effort)."""
    out = []
    i, n = 0, len(rtf)
    while i < n:
        c = rtf[i]
        if c == "\\":
            i += 1
            if i >= n:
                break
            nxt = rtf[i]
            if nxt in "\\{}":
                out.append(nxt if nxt != "\\" else "\\")
                i += 1
            elif nxt == "'":
                out.append("?")
                i += 1
            elif nxt == "*":
                i += 1
            else:
                while i < n and rtf[i].isalpha():
                    i += 1
                while i < n and (rtf[i].isdigit() or rtf[i] == "-"):
                    i += 1
                if i < n and rtf[i] in " ;":
                    i += 1
        elif c in "{}":
            i += 1
        elif c == "\x0c":
            i += 1
            out.append("\n")
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _extract_gpx(data: bytes) -> str:
    """Extract readable waypoints/routes/tracks from a GPX file."""
    root = ET.fromstring(data)
    out = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag in ("wpt", "rtept", "trkpt"):
            parts = []
            lat, lon = el.attrib.get("lat"), el.attrib.get("lon")
            if lat is not None and lon is not None:
                parts.append(f"{lat}, {lon}")
            for child in el:
                ct = child.tag.rsplit("}", 1)[-1]
                if ct in ("name", "desc", "cmt", "time"):
                    txt = "".join(child.itertext()).strip()
                    if txt:
                        parts.append(f"{ct}: {txt}")
            if parts:
                out.append(" | ".join(parts))
    if not out:
        out.append("[GPX file with no readable waypoint text]")
    return "\n".join(out)


def _extract_kml(data: bytes) -> str:
    """Extract names/descriptions/coordinates from a KML (or KMZ document) file."""
    root = ET.fromstring(data)
    out = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag == "name":
            txt = "".join(el.itertext()).strip()
            if txt and len(txt) < 200:
                out.append(f"Placemark: {txt}")
        elif tag == "description":
            txt = "".join(el.itertext()).strip()
            if txt:
                out.append(f"Description: {txt}")
        elif tag == "coordinates":
            txt = " ".join("".join(el.itertext()).split())
            if txt:
                out.append(f"Coordinates: {txt[:2000]}")
    if not out:
        out.append("[KML file with no readable placemark text]")
    return "\n".join(out)


def _extract_kmz(data: bytes) -> str:
    """Read the first KML document inside a KMZ archive."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        candidates = [n for n in zf.namelist() if n.lower().endswith(".kml")]
        if not candidates:
            return "[KMZ archive with no KML document]"
        return _extract_kml(zf.read(candidates[0]))


def _extract_dxf(data: bytes) -> Optional[str]:
    """Pull TEXT/MTEXT-ish values out of an ASCII DXF; None if not parseable."""
    text = _decode_text(data)
    lines = text.splitlines()
    values = []
    for i in range(0, len(lines) - 1, 2):
        code = lines[i].strip()
        value = lines[i + 1].strip()
        if code == "1" and value:
            values.append(value)
    return "\n".join(values) if values else None


def _extract_dbf(data: bytes) -> str:
    """Parse the attribute table of a shapefile (.dbf, dBASE III/IV)."""
    import struct
    if len(data) < 33 or data[0] not in (0x03, 0x30, 0x83, 0x8B, 0xB0):
        return ""
    try:
        num_records = struct.unpack("<I", data[4:8])[0]
        header_len = struct.unpack("<H", data[8:10])[0]
        record_len = struct.unpack("<H", data[10:12])[0]
        if header_len < 32 or record_len < 1:
            return ""
        fields = []
        pos = 32
        while pos + 32 <= header_len and data[pos] != 0x0D:
            name = data[pos:pos + 11].split(b"\x00")[0].decode("utf-8", errors="replace").strip() or f"col{len(fields)}"
            ftype = chr(data[pos + 11])
            fwd = data[pos + 16]
            fields.append((name, ftype, max(1, fwd)))
            pos += 32
        out = [" | ".join(f[0] for f in fields)]
        end = min(len(data), header_len + num_records * record_len)
        for off in range(header_len + 1, end, record_len):
            rec = data[off:off + record_len]
            foff = 0
            vals = []
            for _name, _ftype, fwd in fields:
                seg = rec[foff:foff + fwd]
                seg = seg.split(b"\x00")[0].strip()
                vals.append(seg.decode("utf-8", errors="replace"))
                foff += fwd
            if any(vals):
                out.append(" | ".join(vals))
        return "\n".join(out)
    except Exception:
        return ""


def _extract_las(data: bytes) -> str:
    """Summarize a LiDAR LAS/LAZ point cloud header (point count + version)."""
    if data[:4] != b"LASF":
        return ""
    import struct
    try:
        ver = (data[24], data[25])
        fmt = struct.unpack("<B", data[104:105])[0]
        rec_len = struct.unpack("<H", data[105:107])[0]
        count = struct.unpack("<I", data[107:111])[0]
        if count == 0 and len(data) >= 251:
            count = struct.unpack("<Q", data[247:255])[0]
        return f"[LiDAR point cloud] version {ver[0]}.{ver[1]}, point format {fmt}, record length {rec_len}, {count:,} points"
    except Exception:
        return ""


def extract_text(filename: str, data: bytes) -> str:
    """Return human-readable text extracted from an uploaded file.

    Never raises: unsupported or unreadable content produces a short
    placeholder string so upstream indexing can always proceed.
    """
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if ext == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n".join((page.extract_text() or "") for page in reader.pages)

        if ext == ".epub":
            import ebooklib
            from ebooklib import epub
            book = epub.read_epub(io.BytesIO(data), options={"ignore_ncx": True})
            parts = []
            for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
                html = item.get_content()
                try:
                    parts.append(_extract_html(html))
                except Exception:
                    parts.append(_decode_text(html))
            return "\n\n".join(p for p in parts if p.strip())

        if ext == ".docx":
            import docx
            document = docx.Document(io.BytesIO(data))
            parts = [p.text for p in document.paragraphs if p.text.strip()]
            for table in document.tables:
                for row in table.rows:
                    cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                    parts.append(" | ".join(cells))
            return "\n".join(parts)

        if ext == ".xls":
            import xlrd
            book = xlrd.open_workbook(file_contents=data, on_demand=True)
            out = []
            for sh in book.sheets():
                out.append(f"[Sheet: {sh.name}]")
                for r in range(sh.nrows):
                    vals = [str(sh.cell_value(r, c)) for c in range(sh.ncols)]
                    if any(v.strip() for v in vals):
                        out.append(" | ".join(vals))
            return "\n".join(out)

        if ext == ".xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            out = []
            try:
                for ws in wb.worksheets:
                    out.append(f"[Sheet: {ws.title}]")
                    for row in ws.iter_rows(values_only=True):
                        vals = ["" if v is None else str(v).replace("\n", " ") for v in row]
                        if any(vals):
                            out.append(" | ".join(vals))
            finally:
                wb.close()
            return "\n".join(out)

        if ext == ".pptx":
            from pptx import Presentation
            prs = Presentation(io.BytesIO(data))
            out = []
            for i, slide in enumerate(prs.slides, 1):
                out.append(f"[Slide {i}]")
                for shape in slide.shapes:
                    if shape.has_table:
                        table = shape.table
                        out.append("[Table]")
                        for row in table.rows:
                            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                            out.append(" | ".join(cells))
                    elif hasattr(shape, "text") and shape.text.strip():
                        out.append(shape.text)
                    if shape.has_chart:
                        out.append("[Chart present on this slide]")
            return "\n".join(out)

        if ext in (".odt", ".ods", ".odp", ".fodt"):
            return _extract_opendocument(data)

        if ext == ".gpx":
            return _extract_gpx(data)

        if ext == ".kml":
            return _extract_kml(data)

        if ext == ".kmz":
            return _extract_kmz(data)

        if ext == ".dxf":
            return _extract_dxf(data) or _decode_text(data)

        if ext == ".dbf":
            return _extract_dbf(data)

        if ext in (".las", ".laz"):
            return _extract_las(data)

        if ext in (".html", ".htm"):
            return _extract_html(data)

        if ext in (".csv", ".tsv"):
            delimiter = "\t" if ext == ".tsv" else ","
            text = _decode_text(data)
            try:
                rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
                return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)
            except Exception:
                return text

        if ext == ".rtf":
            return _rtf_to_text(data.decode("latin-1", errors="ignore"))

        if ext in TEXT_EXTENSIONS:
            return _decode_text(data)

        if _looks_like_text(data):
            return _decode_text(data)

        return f"{BINARY_HINT}: {filename or 'file'}]"
    except Exception as e:
        logger.warning("extract_text: could not read %s (%s)", filename, e)
        return f"{BINARY_HINT}: {filename or 'file'}; extraction error]"