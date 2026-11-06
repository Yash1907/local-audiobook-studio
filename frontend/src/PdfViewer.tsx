import {useEffect,useRef,useState} from 'react'
import {getDocument,GlobalWorkerOptions,type PDFDocumentProxy} from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import {ChevronLeft,ChevronRight} from 'lucide-react'

GlobalWorkerOptions.workerSrc=workerUrl

export function PdfViewer({url,initialPage=1}:{url:string;initialPage?:number}){
 const [document,setDocument]=useState<PDFDocumentProxy|null>(null)
 const [page,setPage]=useState(initialPage)
 const [error,setError]=useState('')
 const canvas=useRef<HTMLCanvasElement>(null)
 useEffect(()=>{
  let cancelled=false
  const loading=getDocument({url})
  loading.promise.then(pdf=>{if(!cancelled)setDocument(pdf)}).catch(e=>{if(!cancelled)setError(`PDF could not open: ${e.message}`)})
  return()=>{cancelled=true;loading.destroy();setDocument(null)}
 },[url])
 useEffect(()=>{
  if(!document||!canvas.current)return
  let cancelled=false
  let task:{cancel:()=>void;promise:Promise<unknown>}|undefined
  document.getPage(page).then(pdfPage=>{
   if(cancelled)return
   const viewport=pdfPage.getViewport({scale:1.35})
   const element=canvas.current
   if(!element)return
   element.width=viewport.width;element.height=viewport.height
   const context=element.getContext('2d')
   if(context)task=pdfPage.render({canvas:element,canvasContext:context,viewport})
   task?.promise.catch(()=>{})
  }).catch(e=>setError(`Page could not render: ${e.message}`))
  return()=>{cancelled=true;task?.cancel()}
 },[document,page])
 return <div className="pdf-viewer">{error?<><p className="pdf-fallback">PDF.js could not render this page. Showing the original PDF.</p><iframe title="Original PDF" src={url} className="pdf-frame"/></>:<><div className="pdf-controls"><button disabled={page<=1} onClick={()=>setPage(page-1)} aria-label="Previous PDF page"><ChevronLeft size={17}/></button><span>Page {page} of {document?.numPages||'…'}</span><button disabled={!document||page>=document.numPages} onClick={()=>setPage(page+1)} aria-label="Next PDF page"><ChevronRight size={17}/></button></div><canvas ref={canvas} aria-label={`PDF page ${page}`}/></>}</div>
}
