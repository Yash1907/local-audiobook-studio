import os
from pathlib import Path

os.environ['LAS_HOME']=str(Path(__file__).resolve().parents[1]/'.test-data')

import fitz
from fastapi.testclient import TestClient
from backend.app.main import app, TOKEN
from backend.app.core import connection
from backend.app.extraction import extract, extract_text
from backend.app.normalization import rules, validate
from backend.app.segmentation import split_for_speech
from ebooklib import epub

def test_normalization_preserves_numbers_and_repairs_wrap():
    assert rules('The sys-\ntem achieved 92.7% accuracy [14].') == 'The system achieved ninety-two point seven percent accuracy.'
    assert 'squared' in rules('The value of x² was calculated.')
    assert not validate('Accuracy was 92.7%.', 'Accuracy was 99%.')
    assert not validate('The result was significant.', 'Here is the normalized text: The result was significant.')

def test_pdf_extraction_with_page_reference():
    document=fitz.open()
    page=document.new_page()
    page.insert_text((70,70),'A real PDF paragraph.')
    result=extract(document.tobytes(),'study.pdf')
    assert result.chapters[0][1][0][1]==1
    assert 'real PDF' in result.chapters[0][1][0][0]

def test_text_extraction_preserves_paragraphs():
    result=extract_text(b'First paragraph.\n\nSecond paragraph.','notes.txt')
    assert len(result.chapters[0][1])==2

def test_long_speech_chunks_are_bounded():
    chunks=split_for_speech('A long sentence follows. '*60)
    assert len(chunks)>1
    assert all(len(x)<=420 for x in chunks)

def test_epub_spine_order():
    book=epub.EpubBook()
    book.set_identifier('test-book')
    book.set_title('Test Book')
    book.set_language('en')
    first=epub.EpubHtml(title='First',file_name='first.xhtml',lang='en')
    first.content='<h1>First</h1><p>First chapter.</p>'
    second=epub.EpubHtml(title='Second',file_name='second.xhtml',lang='en')
    second.content='<h1>Second</h1><p>Second chapter.</p>'
    book.add_item(first);book.add_item(second)
    book.add_item(epub.EpubNcx());book.add_item(epub.EpubNav())
    book.spine=[second,first]
    path=Path(os.environ['LAS_HOME'])/'test.epub'
    epub.write_epub(str(path),book)
    result=extract(path.read_bytes(),'book.epub')
    assert [chapter[0] for chapter in result.chapters]==['Second','First']
    path.unlink()

def test_api_import_progress_security_and_delete():
    with TestClient(app) as client:
        denied=client.post('/api/quick-read',json={'text':'Hello'})
        assert denied.status_code==403
        headers={'x-studio-token':TOKEN}
        response=client.post('/api/documents',files={'file':('notes.txt',b'First paragraph.\n\nSecond paragraph.')},headers=headers)
        assert response.status_code==200,response.text
        doc_id=response.json()['id']
        doc=client.get(f'/api/documents/{doc_id}').json()
        assert len(doc['segments'])==2
        segment=doc['segments'][0]['id']
        saved=client.post(f'/api/documents/{doc_id}/progress',json={'segment_id':segment,'offset':1.5},headers=headers)
        assert saved.status_code==200
        assert client.get(f'/api/documents/{doc_id}').json()['progress']['offset']==1.5
        bad=client.get('/api/audio/../../Windows/win.ini')
        assert bad.status_code in (404,405)
        assert client.delete(f'/api/documents/{doc_id}',headers=headers).status_code==200
        assert client.get(f'/api/documents/{doc_id}').status_code==404
