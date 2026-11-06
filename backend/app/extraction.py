import io
import re
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class Extracted:
    title: str
    author: str = ''
    chapters: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

def paragraphs(text):
    return [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

def extract_text(data, name):
    text = data.decode('utf-8-sig', errors='replace')
    if name.lower().endswith('.md'):
        text = re.sub(r'(?m)^#{1,6}\s+', '', text)
    return Extracted(Path(name).stem, chapters=[('Content', [(p, None) for p in paragraphs(text)])])

def extract_pdf(data, name):
    import fitz
    doc = fitz.open(stream=data, filetype='pdf')
    title = doc.metadata.get('title') or Path(name).stem
    result = Extracted(title, doc.metadata.get('author') or '')
    pages = []
    for index, page in enumerate(doc):
        blocks = [b for b in page.get_text('blocks') if len(b) > 6 and b[6] == 0]
        width = page.rect.width
        left = [b for b in blocks if b[0] < width * .48 and b[2] < width * .6]
        right = [b for b in blocks if b[0] > width * .4]
        if left and right and len(left) + len(right) >= len(blocks) * .75:
            ordered = sorted(left, key=lambda b:b[1]) + sorted(right, key=lambda b:b[1])
            ordered += [b for b in blocks if b not in ordered]
        else:
            ordered = sorted(blocks, key=lambda b:(round(b[1]/12), b[0]))
        items = [(b[4].strip(), index + 1) for b in ordered if b[4].strip()]
        if not items:
            try:
                import pytesseract
                from PIL import Image
                pix = page.get_pixmap(matrix=fitz.Matrix(2,2))
                ocr = pytesseract.image_to_string(Image.open(io.BytesIO(pix.tobytes('png')))).strip()
                if ocr:
                    items = [(ocr, index + 1)]
                else:
                    result.warnings.append(f'Page {index+1} has no readable text.')
            except Exception:
                result.warnings.append(f'Page {index+1} needs Tesseract OCR.')
        pages.extend(items)
    result.chapters = [('Document', pages)]
    return result

def extract_epub(data, name):
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    book = epub.read_epub(io.BytesIO(data))
    metadata = lambda key: book.get_metadata('DC', key)
    title = metadata('title')[0][0] if metadata('title') else Path(name).stem
    author = metadata('creator')[0][0] if metadata('creator') else ''
    result = Extracted(title, author)
    for item_id, _ in book.spine:
        item = book.get_item_with_id(item_id)
        if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        for tag in soup(['script','style','nav']): tag.decompose()
        heading = soup.find(['h1','h2','h3','title'])
        heading_text = heading.get_text(' ', strip=True) if heading else f'Chapter {len(result.chapters)+1}'
        chunks = [x.get_text(' ', strip=True) for x in soup.find_all(['p','h1','h2','h3','li'])]
        chunks = [x for x in chunks if x]
        if chunks:
            result.chapters.append((heading_text, [(x,None) for x in chunks]))
    return result

def extract_image(data, name):
    from PIL import Image
    import pytesseract
    text = pytesseract.image_to_string(Image.open(io.BytesIO(data))).strip()
    if not text:
        raise ValueError('OCR found no text. Check the image or install Tesseract.')
    result = Extracted(Path(name).stem, chapters=[('OCR text', [(p,None) for p in paragraphs(text)])])
    if len(text) < 30:
        result.warnings.append('Very little text was recognized; review it before narration.')
    return result

def extract(data, name):
    suffix = Path(name).suffix.lower()
    if suffix == '.pdf': return extract_pdf(data, name)
    if suffix == '.epub': return extract_epub(data, name)
    if suffix in ('.png','.jpg','.jpeg','.webp'): return extract_image(data, name)
    if suffix in ('.txt','.md'): return extract_text(data, name)
    raise ValueError('Supported files: PDF, EPUB, TXT, Markdown, PNG, JPEG, WEBP')
