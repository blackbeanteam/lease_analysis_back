import fitz, hashlib
from typing import List
from ..models.extract_models import ExtractResult, ExtractMeta, ExtractPage, TextBlock

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def extract_from_pdf_bytes(filename: str, data: bytes) -> ExtractResult:
    filehash = _sha256(data)
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        return ExtractResult(
            ok=False,
            meta=ExtractMeta(filename=filename, page_count=0, sha256=filehash),
            pages=[],
            error=f"Cannot open as PDF: {e}",
        )

    pages: List[ExtractPage] = []
    for i in range(len(doc)):
        page = doc[i]
        text = page.get_text("text")
        blocks_raw = page.get_text("blocks")
        blocks = []
        for b in blocks_raw:
            x0, y0, x1, y1, t = b[0], b[1], b[2], b[3], b[4]
            if isinstance(t, str) and t.strip():
                blocks.append(TextBlock(bbox=[float(x0), float(y0), float(x1), float(y1)], text=t.strip()))
        pages.append(ExtractPage(page=i+1, text=text, blocks=blocks))

    meta = ExtractMeta(filename=filename, page_count=len(doc), sha256=filehash)
    return ExtractResult(ok=True, meta=meta, pages=pages)
