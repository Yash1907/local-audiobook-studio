import re

def split_for_speech(text, limit=420):
    text=text.strip()
    if not text: return []
    if len(text)<=limit: return [text]
    boundaries=re.split(r'(?<=[.!?])\s+(?=[\"“A-Z0-9])',text)
    chunks=[]
    current=''
    for sentence in boundaries:
        if len(sentence)>limit:
            if current: chunks.append(current); current=''
            words=sentence.split()
            piece=''
            for word in words:
                if len(piece)+len(word)+1>limit and piece:
                    chunks.append(piece);piece=''
                piece=(piece+' '+word).strip()
            if piece: current=piece
        elif len(current)+len(sentence)+1>limit:
            chunks.append(current)
            current=sentence
        else:
            current=(current+' '+sentence).strip()
    if current: chunks.append(current)
    return chunks
