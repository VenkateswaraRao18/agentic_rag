from pathlib import Path



from bs4 import BeautifulSoup





def parse_html(path: Path) -> str:

    html = path.read_text(encoding="utf-8", errors="ignore")

    soup = BeautifulSoup(html, "html.parser")

    return soup.get_text(separator=" ", strip=True)





def parse_plain_document(path: Path) -> str:

    """

    Plain-text extraction for non-PDF types. PDFs should use DocuWeave in build_index.

    """

    suffix = path.suffix.lower()

    if suffix in {".html", ".htm"}:

        return parse_html(path)

    return path.read_text(encoding="utf-8", errors="ignore")


