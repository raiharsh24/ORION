import os
from typing import List, Dict, Any, Optional
from loguru import logger
from app.orion.vectordb import VectorDB
from app.memory.embeddings import EmbeddingsManager

class DocumentIndexer:
    """
    Discovers, chunks, embeds, and stores workspace text/code documents and PDFs.
    """
    def __init__(self, vector_db: VectorDB, embeddings: EmbeddingsManager) -> None:
        self.vector_db = vector_db
        self.embeddings = embeddings
        self.supported_extensions = {
            ".md", ".txt", ".pdf", ".py", ".js", ".ts", ".tsx", ".jsx", ".json"
        }
        self.ignore_folders = {
            ".git", "node_modules", ".venv", "venv", "__pycache__", 
            ".pytest_cache", "dist", "build", "target", ".next", ".cache"
        }

    def _parse_pdf(self, file_path: str) -> str:
        """
        Extracts raw text pages from PDF files. Falls back safely if pypdf is missing.
        """
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            text = ""
            for idx, page in enumerate(reader.pages):
                text += page.extract_text() or ""
            return text
        except ImportError:
            logger.warning(f"pypdf package is missing. Cannot parse PDF at: {file_path}")
            return ""
        except Exception as e:
            logger.error(f"Error parsing PDF '{file_path}': {str(e)}")
            return ""

    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 150) -> List[str]:
        """
        Splits text content into character blocks with sliding overlap bounds.
        """
        chunks = []
        if not text:
            return chunks
        if len(text) <= chunk_size:
            return [text]

        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            
            # Find whitespace character within overlap bounds to split cleanly
            if end < len(text):
                lookback = text[max(start, end - overlap):end]
                split_idx = max(lookback.rfind('\n'), lookback.rfind(' '))
                if split_idx != -1:
                    end = max(start, end - overlap) + split_idx + 1

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end
        return chunks

    async def index_file(self, file_path: str, project_name: str) -> int:
        """
        Reads, chunks, embeds, and saves file content.
        Returns the number of created chunks.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.supported_extensions:
            return 0

        content = ""
        try:
            if ext == ".pdf":
                content = self._parse_pdf(file_path)
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
        except Exception as e:
            logger.error(f"Error reading file '{file_path}': {str(e)}")
            return 0

        if not content.strip():
            return 0

        chunks = self.chunk_text(content)
        if not chunks:
            return 0

        ids = []
        embeddings = []
        metadatas = []
        documents = []

        # Relative path for cleaner identifiers and metadata
        file_path_clean = os.path.abspath(file_path)

        for idx, chunk in enumerate(chunks):
            # Deterministic unique ID based on file path and chunk index
            chunk_id = f"{file_path_clean}#chunk{idx}"
            
            # Generate embedding
            vector = await self.embeddings.embed_text(chunk)

            ids.append(chunk_id)
            embeddings.append(vector)
            metadatas.append({
                "file_path": file_path_clean,
                "project_name": project_name,
                "file_type": ext.lstrip("."),
                "chunk_index": idx
            })
            documents.append(chunk)

        # Store in Vector DB
        try:
            self.vector_db.add(
                ids=ids,
                embeddings=embeddings,
                metadatas=metadatas,
                documents=documents
            )
            return len(chunks)
        except Exception as e:
            logger.error(f"Failed to add file chunks to vector store: {str(e)}")
            return 0

    async def index_directory(self, dir_path: str, project_name: Optional[str] = None) -> int:
        """
        Recursively scans and indexes files within a folder.
        """
        target_dir = os.path.abspath(dir_path)
        if not os.path.exists(target_dir) or not os.path.isdir(target_dir):
            logger.error(f"Index target path {target_dir} is invalid.")
            return 0

        proj_name = project_name or os.path.basename(target_dir)
        total_chunks = 0

        for root, dirs, files in os.walk(target_dir):
            # Prune ignored folders in-place
            dirs[:] = [d for d in dirs if d not in self.ignore_folders]

            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in self.supported_extensions:
                    file_path = os.path.join(root, f)
                    chunks_added = await self.index_file(file_path, proj_name)
                    total_chunks += chunks_added

        logger.info(f"Indexing finished. Added {total_chunks} chunks for project '{proj_name}'.")
        return total_chunks
