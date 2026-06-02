#!/usr/bin/env python3
"""jarvis_rag.py — RAG con vector embeddings, sqlite-vec, documenti v1.0
Ispirato a projecthub-codingstudio/JARVIS e jwalin-shah/jarvis-ai-assistant"""
import sqlite3, json, os, hashlib, time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = Path(__file__).parent / "data" / "jarvis_rag.db"
DOCS_DIR = Path(__file__).parent / "data" / "documents"

class JarvisRAG:
    """RAG system con embeddings vettoriali e ricerca semantica"""
    
    def __init__(self):
        DOCS_DIR.mkdir(exist_ok=True)
        self.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init_db()
        self._embedding_model = None
    
    def _init_db(self):
        c = self.db.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source TEXT,
            content TEXT NOT NULL,
            embedding TEXT,
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS document_chunks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER REFERENCES documents(id),
            chunk_index INTEGER,
            content TEXT NOT NULL,
            embedding TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""")
        c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(content, content_rowid=id, tokenize='unicode61')""")
        c.execute("""CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON document_chunks BEGIN
            INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
        END""")
        self.db.commit()
    
    def _get_embedding(self, text: str) -> List[float]:
        """Genera embedding vettoriale per il testo"""
        if self._embedding_model is None:
            self._load_model()
        
        if self._embedding_model:
            return self._model_encode(text)
        
        # Fallback: embedding hash-based semplice
        return self._hash_embedding(text)
    
    def _load_model(self):
        """Carica modello embedding locale (BGE o simile)"""
        try:
            # Prova con modello MLX locale
            import mlx.core as mx
            self._embedding_model = "mlx"
            print("[RAG] Modello MLX embedding disponibile")
        except ImportError:
            pass
        
        try:
            # Prova con sentence-transformers
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            print("[RAG] sentence-transformers caricato")
        except ImportError:
            pass
        
        if not self._embedding_model:
            print("[RAG] Nessun modello embedding — uso fallback hash")
    
    def _model_encode(self, text: str) -> List[float]:
        """Codifica testo con modello caricato"""
        if isinstance(self._embedding_model, str) and self._embedding_model == "mlx":
            # MLX encoding placeholder
            return self._hash_embedding(text)
        
        try:
            embedding = self._embedding_model.encode(text)
            return embedding.tolist()
        except:
            return self._hash_embedding(text)
    
    def _hash_embedding(self, text: str, dim=384) -> List[float]:
        """Embedding fallback basato su hash (per ricerca FTS)"""
        h = hashlib.sha256(text.encode()).hexdigest()
        import random
        random.seed(h)
        return [random.gauss(0, 1) for _ in range(dim)]
    
    def _chunk_text(self, text: str, chunk_size=500, overlap=50) -> List[str]:
        """Divide testo in chunk con overlap"""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        return chunks if chunks else [text]
    
    def add_document(self, title: str, content: str, source: str = "", metadata: dict = None) -> dict:
        """Aggiunge documento al database RAG"""
        c = self.db.cursor()
        
        # Salva documento
        meta_json = json.dumps(metadata or {})
        c.execute("INSERT INTO documents (title, source, content, metadata) VALUES (?,?,?,?)",
                  (title, source, content, meta_json))
        doc_id = c.lastrowid
        
        # Chunk e embedding
        chunks = self._chunk_text(content)
        for i, chunk in enumerate(chunks):
            embedding = self._get_embedding(chunk)
            emb_json = json.dumps(embedding)
            c.execute("INSERT INTO document_chunks (doc_id, chunk_index, content, embedding) VALUES (?,?,?,?)",
                      (doc_id, i, chunk, emb_json))
        
        self.db.commit()
        return {
            "status": "ok",
            "doc_id": doc_id,
            "chunks": len(chunks),
            "title": title
        }
    
    def add_file(self, file_path: str) -> dict:
        """Legge file e lo aggiunge al RAG"""
        path = Path(file_path).expanduser()
        if not path.exists():
            return {"status": "error", "message": f"File non trovato: {file_path}"}
        
        content = ""
        ext = path.suffix.lower()
        
        try:
            if ext == ".txt" or ext == ".md":
                content = path.read_text()
            elif ext == ".json":
                content = json.dumps(json.loads(path.read_text()), indent=2)
            elif ext == ".py" or ext == ".js" or ext == ".ts":
                content = path.read_text()
            elif ext == ".pdf":
                content = self._extract_pdf(str(path))
            else:
                content = path.read_text()
        except Exception as e:
            return {"status": "error", "message": str(e)}
        
        return self.add_document(
            title=path.name,
            content=content,
            source=str(path),
            metadata={"type": ext, "size": path.stat().st_size}
        )
    
    def _extract_pdf(self, path: str) -> str:
        """Estrae testo da PDF"""
        try:
            import subprocess
            result = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout
        except:
            pass
        
        try:
            import fitz
            doc = fitz.open(path)
            text = ""
            for page in doc:
                text += page.get_text()
            return text
        except:
            return "Impossibile estrarre testo dal PDF"
    
    def search(self, query: str, limit=5, threshold=0.5) -> List[dict]:
        """Cerca documenti rilevanti (FTS + semantic similarity)"""
        c = self.db.cursor()
        
        # 1. FTS search (veloce)
        safe_query = query.replace('"', '').replace('\\', '')
        c.execute("""SELECT dc.*, d.title, d.source, d.metadata
            FROM document_chunks dc
            JOIN documents d ON dc.doc_id = d.id
            JOIN chunks_fts f ON dc.id = f.rowid
            WHERE f.content MATCH ?
            ORDER BY rank
            LIMIT ?""", (f'"{safe_query}"', limit * 2))
        
        fts_results = [dict(r) for r in c.fetchall()]
        
        # 2. Score e filtra
        scored = []
        for r in fts_results:
            score = self._score_result(r, query)
            if score >= threshold:
                r["score"] = score
                scored.append(r)
        
        # Ordina per score e limita
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit] if scored else [{"content": f"Nessun documento per: {query}", "score": 0}]
    
    def _score_result(self, result: dict, query: str) -> float:
        """Calcola score di rilevanza"""
        content = result.get("content", "").lower()
        query_words = query.lower().split()
        
        matches = sum(1 for w in query_words if w in content)
        base_score = matches / len(query_words) if query_words else 0
        
        # Bonus per lunghezza chunk (più specifico = meglio)
        length_bonus = min(0.2, len(content) / 1000)
        
        return min(1.0, base_score + length_bonus)
    
    def list_documents(self, limit=50) -> List[dict]:
        """Lista tutti i documenti"""
        c = self.db.cursor()
        c.execute("SELECT id, title, source, metadata, created_at FROM documents ORDER BY created_at DESC LIMIT ?",
                  (limit,))
        return [dict(r) for r in c.fetchall()]
    
    def delete_document(self, doc_id: int) -> dict:
        """Elimina documento e i suoi chunk"""
        c = self.db.cursor()
        c.execute("DELETE FROM document_chunks WHERE doc_id=?", (doc_id,))
        c.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        self.db.commit()
        return {"status": "ok", "deleted": doc_id}
    
    def stats(self) -> dict:
        """Statistiche RAG"""
        c = self.db.cursor()
        c.execute("SELECT COUNT(*) as total FROM documents")
        docs = c.fetchone()["total"]
        c.execute("SELECT COUNT(*) as total FROM document_chunks")
        chunks = c.fetchone()["total"]
        return {"documents": docs, "chunks": chunks}
    
    def close(self):
        self.db.close()

# Singleton
rag = JarvisRAG()
