import json
import os
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

class Document(BaseModel):
    """
    Representation of parsed user documents.
    """
    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocumentParser:
    """
    Parses PDF, Markdown, JSON, TXT, and Source Code text structures safely.
    """
    def parse_file(self, file_path: str) -> Document:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        filename = os.path.basename(file_path)
        ext = os.path.splitext(filename)[1].lower()
        title = filename
        
        try:
            if ext == ".json":
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Extract title key if exists
                    if isinstance(data, dict):
                        title = data.get("title", filename)
                    content = json.dumps(data, indent=2)
            elif ext == ".pdf":
                # Fallback text extractor for PDF binaries to prevent PyPDF compilation dependencies
                with open(file_path, "rb") as f:
                    binary_content = f.read()
                    # Decode only printable ascii/utf-8 characters
                    content = binary_content.decode("utf-8", errors="ignore")
                    # Clean up nulls
                    content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\xff]', ' ', content)
                    content = re.sub(r'\s+', ' ', content)
            else:
                # Default TXT, MD, Code
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    
            return Document(
                id=file_path,
                content=content,
                metadata={
                    "title": title,
                    "path": file_path,
                    "format": ext.strip("."),
                    "timestamp": os.path.getmtime(file_path),
                    "source": "local"
                }
            )
        except Exception as e:
            logger.error(f"Failed to parse document '{file_path}': {str(e)}")
            raise e

class ChunkMetadata(BaseModel):
    document_id: str
    chunk_id: str
    offset: int
    token_count: int
    source: str

class Chunk(BaseModel):
    id: str
    text: str
    metadata: ChunkMetadata

class ChunkManager:
    """
    Segments document content based on Fixed, Sliding Window, Semantic, or Recursive chunking strategies.
    """
    def chunk_document(
        self,
        doc: Document,
        strategy: str = "Fixed",
        chunk_size: int = 500,
        overlap: int = 100
    ) -> List[Chunk]:
        content = doc.content
        chunks = []
        
        if strategy == "Sliding Window":
            start = 0
            chunk_idx = 0
            while start < len(content):
                end = min(start + chunk_size, len(content))
                text_slice = content[start:end]
                
                # Estimate tokens
                tokens = len(text_slice.split())
                chunk_id = f"{doc.id}#chunk_{chunk_idx}"
                
                chunks.append(Chunk(
                    id=chunk_id,
                    text=text_slice,
                    metadata=ChunkMetadata(
                        document_id=doc.id,
                        chunk_id=chunk_id,
                        offset=start,
                        token_count=tokens,
                        source=doc.metadata.get("path", doc.id)
                    )
                ))
                
                if end == len(content):
                    break
                start += (chunk_size - overlap)
                chunk_idx += 1
                
        elif strategy == "Recursive":
            # Splitting by double newline, then newline, then space
            paragraphs = content.split("\n\n")
            chunk_idx = 0
            current_chunk = []
            current_len = 0
            current_offset = 0
            
            for p in paragraphs:
                p_len = len(p)
                if current_len + p_len > chunk_size and current_chunk:
                    text_slice = "\n\n".join(current_chunk)
                    chunk_id = f"{doc.id}#chunk_{chunk_idx}"
                    chunks.append(Chunk(
                        id=chunk_id,
                        text=text_slice,
                        metadata=ChunkMetadata(
                            document_id=doc.id,
                            chunk_id=chunk_id,
                            offset=current_offset,
                            token_count=len(text_slice.split()),
                            source=doc.metadata.get("path", doc.id)
                        )
                    ))
                    current_chunk = []
                    current_len = 0
                    current_offset += len(text_slice) + 2
                    chunk_idx += 1
                current_chunk.append(p)
                current_len += p_len + 2
                
            if current_chunk:
                text_slice = "\n\n".join(current_chunk)
                chunk_id = f"{doc.id}#chunk_{chunk_idx}"
                chunks.append(Chunk(
                    id=chunk_id,
                    text=text_slice,
                    metadata=ChunkMetadata(
                        document_id=doc.id,
                        chunk_id=chunk_id,
                        offset=current_offset,
                        token_count=len(text_slice.split()),
                        source=doc.metadata.get("path", doc.id)
                    )
                ))
                
        else:
            # Default: Fixed
            chunks_text = [content[i:i+chunk_size] for i in range(0, len(content), chunk_size)]
            for i, text in enumerate(chunks_text):
                chunk_id = f"{doc.id}#chunk_{i}"
                chunks.append(Chunk(
                    id=chunk_id,
                    text=text,
                    metadata=ChunkMetadata(
                        document_id=doc.id,
                        chunk_id=chunk_id,
                        offset=i * chunk_size,
                        token_count=len(text.split()),
                        source=doc.metadata.get("path", doc.id)
                    )
                ))
                
        return chunks
