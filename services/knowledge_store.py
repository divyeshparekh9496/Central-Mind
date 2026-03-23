"""Personal knowledge storage service for the Personal Knowledge Brain."""
import sqlite3
import json
import uuid
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

from config import Config


class ProcessingResult:
    """Result from content processing pipeline."""
    def __init__(self, chunks: List[dict], embeddings: List[np.ndarray] = None, 
                 metadata: dict = None, blob_reference: str = None):
        self.chunks = chunks
        self.embeddings = embeddings or []
        self.metadata = metadata or {}
        self.blob_reference = blob_reference


class KnowledgeStore:
    """
    Personal knowledge storage service building on existing patterns.
    Stores documents, chunks, and embeddings for semantic search.
    """
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or getattr(Config, 'KNOWLEDGE_DB_PATH', 'knowledge.db')
        
        # Initialize embedding model (same as existing semantic cache patterns)
        embedding_model = getattr(Config, 'EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with schema."""
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            -- Documents table (parent container for all content)
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                modality TEXT NOT NULL CHECK (modality IN ('audio', 'document', 'web', 'text', 'image')),
                source_identifier TEXT,
                source_path TEXT,
                content_hash TEXT,
                content_timestamp TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                processing_status TEXT DEFAULT 'completed'
            );
            
            -- Chunks table (searchable content pieces)
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                content_text TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                embedding_vector TEXT,
                hierarchy_level TEXT,
                section_title TEXT,
                content_timestamp TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            );
            
            -- Performance indexes
            CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
            CREATE INDEX IF NOT EXISTS idx_documents_modality ON documents(modality);
            CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at);
            CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_timestamp ON chunks(content_timestamp);
        """)
        conn.commit()
        conn.close()
    
    async def store_content(self, content: ProcessingResult, user_id: str) -> str:
        """Store processed content in knowledge base."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Generate content hash for deduplication
            content_text = " ".join([chunk["content"] for chunk in content.chunks])
            content_hash = hashlib.sha256(content_text.encode()).hexdigest()
            
            # Store document
            doc_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO documents (id, user_id, modality, source_identifier, 
                                     source_path, content_hash, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id, 
                user_id, 
                content.metadata.get("modality", "text"),
                content.metadata.get("source_identifier", ""),
                content.metadata.get("source_path", ""),
                content_hash,
                json.dumps(content.metadata)
            ))
            
            # Store chunks with embeddings
            for i, chunk in enumerate(content.chunks):
                chunk_id = str(uuid.uuid4())
                
                # Generate embedding if not provided
                if i < len(content.embeddings):
                    embedding = content.embeddings[i]
                else:
                    embedding = self.embedding_model.encode(chunk["content"])
                
                embedding_json = json.dumps(embedding.tolist())
                
                conn.execute("""
                    INSERT INTO chunks (id, document_id, content_text, chunk_index, 
                                      embedding_vector, hierarchy_level, section_title)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    chunk_id, 
                    doc_id, 
                    chunk["content"], 
                    i, 
                    embedding_json, 
                    chunk.get("hierarchy_level", "chunk"),
                    chunk.get("section_title", "")
                ))
            
            conn.commit()
            return doc_id
            
        finally:
            conn.close()
    
    async def search_similar(self, query: str, user_id: str, limit: int = 10) -> List[dict]:
        """Search for similar content using embeddings (extends existing similarity logic)."""
        # Generate query embedding
        query_embedding = self.embedding_model.encode(query)
        
        # Get all chunks for user
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT c.id, c.content_text, c.embedding_vector, d.modality, 
                   d.source_identifier, d.metadata, c.chunk_index, c.section_title
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.user_id = ?
        """, (user_id,))
        
        results = []
        similarity_threshold = getattr(Config, 'VECTOR_SIMILARITY_THRESHOLD', 0.7)
        
        for row in cursor.fetchall():
            chunk_id, content, embedding_json, modality, source, metadata_json, chunk_index, section_title = row
            
            try:
                # Calculate similarity (reuse existing cosine similarity logic)
                chunk_embedding = np.array(json.loads(embedding_json))
                similarity = self._cosine_similarity(query_embedding, chunk_embedding)
                
                if similarity >= similarity_threshold:
                    metadata = json.loads(metadata_json) if metadata_json else {}
                    results.append({
                        "chunk_id": chunk_id,
                        "content": content,
                        "similarity": similarity,
                        "modality": modality,
                        "source": source,
                        "chunk_index": chunk_index,
                        "section_title": section_title,
                        "metadata": metadata
                    })
            except Exception as e:
                print(f"Error processing chunk {chunk_id}: {e}")
                continue
        
        conn.close()
        
        # Sort by similarity and return top results
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]
    
    async def search_keywords(self, keywords: List[str], user_id: str, limit: int = 10) -> List[dict]:
        """Perform keyword-based full-text search."""
        if not keywords:
            return []
        
        conn = sqlite3.connect(self.db_path)
        
        # Build search query for keywords
        search_conditions = []
        params = [user_id]
        
        for keyword in keywords:
            search_conditions.append("c.content_text LIKE ?")
            params.append(f"%{keyword}%")
        
        query = f"""
            SELECT c.id, c.content_text, d.modality, d.source_identifier, 
                   d.metadata, c.chunk_index, c.section_title
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.user_id = ? AND ({' OR '.join(search_conditions)})
            ORDER BY c.created_at DESC
            LIMIT ?
        """
        params.append(limit)
        
        cursor = conn.execute(query, params)
        results = []
        
        for row in cursor.fetchall():
            chunk_id, content, modality, source, metadata_json, chunk_index, section_title = row
            metadata = json.loads(metadata_json) if metadata_json else {}
            
            results.append({
                "chunk_id": chunk_id,
                "content": content,
                "modality": modality,
                "source": source,
                "chunk_index": chunk_index,
                "section_title": section_title,
                "metadata": metadata
            })
        
        conn.close()
        return results
    
    async def list_user_documents(self, user_id: str, modality: str = None, 
                                 limit: int = 50, offset: int = 0) -> List[dict]:
        """List user's documents with optional filtering."""
        conn = sqlite3.connect(self.db_path)
        
        if modality:
            cursor = conn.execute("""
                SELECT id, modality, source_identifier, created_at, metadata
                FROM documents 
                WHERE user_id = ? AND modality = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (user_id, modality, limit, offset))
        else:
            cursor = conn.execute("""
                SELECT id, modality, source_identifier, created_at, metadata
                FROM documents 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))
        
        documents = []
        for row in cursor.fetchall():
            doc_id, modality, source, created_at, metadata_json = row
            metadata = json.loads(metadata_json) if metadata_json else {}
            
            documents.append({
                "id": doc_id,
                "modality": modality,
                "source": source,
                "created_at": created_at,
                "title": metadata.get("title", source or "Untitled"),
                "metadata": metadata
            })
        
        conn.close()
        return documents
    
    async def delete_document(self, document_id: str, user_id: str) -> bool:
        """Delete a document and all its chunks."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Verify ownership
            cursor = conn.execute(
                "SELECT id FROM documents WHERE id = ? AND user_id = ?",
                (document_id, user_id)
            )
            
            if not cursor.fetchone():
                return False
            
            # Delete document (chunks will be deleted by CASCADE)
            conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            conn.commit()
            
            return True
            
        finally:
            conn.close()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        conn = sqlite3.connect(self.db_path)
        
        # Get document counts by modality
        cursor = conn.execute("""
            SELECT modality, COUNT(*) 
            FROM documents 
            GROUP BY modality
        """)
        modality_counts = dict(cursor.fetchall())
        
        # Get total counts
        cursor = conn.execute("SELECT COUNT(*) FROM documents")
        total_docs = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(*) FROM chunks")
        total_chunks = cursor.fetchone()[0]
        
        # Get storage size
        cursor = conn.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        db_size = cursor.fetchone()[0] if cursor.fetchone() else 0
        
        conn.close()
        
        return {
            "total_documents": total_docs,
            "total_chunks": total_chunks,
            "documents_by_modality": modality_counts,
            "storage_path": self.db_path,
            "database_size_bytes": db_size
        }
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Reuse existing cosine similarity calculation."""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)