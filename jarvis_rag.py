#!/usr/bin/env python3
"""jarvis_rag.py — RAG con vector embeddings, ricerca semantica e ibrida v2.0
Ispirato a F13 (German gov AI) e projecthub-codingstudio/JARVIS
Features:
- Embedding reali con sentence-transformers o MLX
- Ricerca ibrida: FTS (keyword) + cosine similarity (semantica)
- Ingestione automatica di file e cartelle
- Auto-embedding all'avvio per chunk senza embedding"""
import sqlite3, json, os, hashlib, time, threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import numpy as np

DB_PATH = Path(__file__).parent / "data" / "jarvis_rag.db"
DOCS_DIR = Path(__file__).parent / "data" / "documents"

class JarvisRAG:
    """RAG system con embeddings vettoriali e ricerca semantica ibrida"""
    
    def __init__(self):
        DOCS_DIR.mkdir(exist_ok=True)
        self.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_db()
        self._model = None
        self._model_name = None
        self._load_model()
        self._auto_embed_pending()
    
    def _init_db(self):
        c = self.db.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source TEXT,
            content TEXT NOT NULL,
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
        try:
            c.execute("""CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON document_chunks BEGIN
                INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content);
            END""")
        except:
            pass
        self.db.commit()
    
    def _load_model(self):
        """Carica modello embedding: sentence-transformers (reale) > MLX > fallback"""
        for name, loader in [
            ("sentence-transformers", self._try_sentence_transformers),
            ("mlx", self._try_mlx),
        ]:
            model = loader()
            if model is not None:
                self._model = model
                self._model_name = name
                print(f"[RAG] Modello '{name}' caricato con successo")
                return
        print("[RAG] Nessun modello embedding — vettori casuali (solo FTS)")
    
    def _try_mlx(self):
        try:
            import mlx.core as mx
            from mlx_lm import generate
            return "mlx"
        except ImportError:
            return None
    
    def _try_sentence_transformers(self):
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            return model
        except ImportError:
            return None
    
    def _encode(self, text: str) -> np.ndarray:
        """Genera embedding vettoriale reale o fallback deterministico"""
        if self._model is None:
            return self._hash_vector(text)
        if self._model_name == "mlx":
            return self._hash_vector(text)
        try:
            emb = self._model.encode([text], normalize_embeddings=True)
            return emb[0]
        except:
            return self._hash_vector(text)
    
    def _hash_vector(self, text: str, dim=384) -> np.ndarray:
        """Vettore deterministico basato su hash (riproducibile)"""
        h = hashlib.sha256(text.encode()).hexdigest()
        rng = np.random.default_rng(int(h[:16], 16))
        vec = rng.normal(0, 1, dim).astype(np.float32)
        return vec / np.linalg.norm(vec)
    
    def _chunk_text(self, text: str, chunk_size=500, overlap=50) -> List[str]:
        """Divide testo in chunk con overlap intelligente (prova a spezzare su newline/periodo)"""
        if len(text.split()) <= chunk_size:
            return [text.strip()]
        
        import re
        # Prova a spezzare per paragrafi
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        chunks = []
        current = []
        current_len = 0
        
        for para in paragraphs:
            para_words = len(para.split())
            if current_len + para_words <= chunk_size:
                current.append(para)
                current_len += para_words
            else:
                if current:
                    chunks.append('\n\n'.join(current))
                # Se un paragrafo è più lungo del chunk, spezza per frasi
                if para_words > chunk_size:
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    for sent in sentences:
                        sent_words = len(sent.split())
                        if current_len + sent_words <= chunk_size:
                            current.append(sent)
                            current_len += sent_words
                        else:
                            if current:
                                chunks.append(' '.join(current))
                            current = [sent]
                            current_len = sent_words
                else:
                    current = [para]
                    current_len = para_words
        
        if current:
            chunks.append('\n\n'.join(current))
        
        return [c.strip() for c in chunks if c.strip()] or [text.strip()]
    
    def add_document(self, title: str, content: str, source: str = "", metadata: dict = None) -> dict:
        """Aggiunge documento al database RAG con embedding"""
        if not content.strip():
            return {"status": "error", "message": "Contenuto vuoto"}
        
        with self._lock:
            c = self.db.cursor()
            meta_json = json.dumps(metadata or {})
            c.execute("INSERT INTO documents (title, source, content, metadata) VALUES (?,?,?,?)",
                      (title[:500], source, content, meta_json))
            doc_id = c.lastrowid
            
            chunks = self._chunk_text(content)
            for i, chunk in enumerate(chunks):
                embedding = self._encode(chunk).tolist()
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
            if ext == ".txt":
                content = path.read_text('utf-8', errors='replace')
            elif ext == ".md":
                content = path.read_text('utf-8', errors='replace')
            elif ext == ".json":
                raw = path.read_text('utf-8', errors='replace')
                content = json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
            elif ext in (".py", ".js", ".ts", ".swift", ".rs", ".go", ".java", ".c", ".h", ".cpp", ".rb", ".sh"):
                content = path.read_text('utf-8', errors='replace')
            elif ext == ".pdf":
                content = self._extract_pdf(str(path))
            elif ext in (".csv", ".tsv"):
                content = path.read_text('utf-8', errors='replace')
            elif ext in (".html", ".htm", ".xml", ".svg"):
                content = path.read_text('utf-8', errors='replace')
            elif ext == ".docx":
                content = self._extract_docx(str(path))
            else:
                content = path.read_text('utf-8', errors='replace')
        except Exception as e:
            return {"status": "error", "message": str(e)}
        
        if not content.strip():
            return {"status": "error", "message": "File vuoto o non leggibile"}
        
        return self.add_document(
            title=path.name,
            content=content,
            source=str(path),
            metadata={"type": ext, "size": path.stat().st_size}
        )
    
    def add_folder(self, folder_path: str, recursive=True) -> dict:
        """Indicizza tutti i file supportati in una cartella"""
        path = Path(folder_path).expanduser()
        if not path.is_dir():
            return {"status": "error", "message": f"Cartella non trovata: {folder_path}"}
        
        SUPPORTED = {'.txt','.md','.json','.pdf','.py','.js','.ts','.swift','.rs',
                     '.go','.java','.c','.h','.cpp','.rb','.sh','.csv','.html',
                     '.htm','.xml','.svg','.docx'}
        
        if recursive:
            files = [f for f in path.rglob('*') if f.suffix.lower() in SUPPORTED and f.is_file()]
        else:
            files = [f for f in path.glob('*') if f.suffix.lower() in SUPPORTED and f.is_file()]
        
        # Skip already-indexed files
        c = self.db.cursor()
        c.execute("SELECT DISTINCT source FROM documents WHERE source IS NOT NULL AND source != ''")
        indexed = {row['source'] for row in c.fetchall()}
        
        results = []
        for f in files:
            source = str(f)
            if source in indexed:
                results.append({"file": f.name, "status": "skipped (already indexed)"})
                continue
            result = self.add_file(source)
            results.append({"file": f.name, "status": result.get("status", "error"), "chunks": result.get("chunks", 0)})
        
        indexed_count = sum(1 for r in results if r.get("status") == "ok")
        return {
            "status": "ok",
            "total": len(files),
            "indexed": indexed_count,
            "skipped": len(files) - indexed_count,
            "results": results
        }
    
    def _extract_pdf(self, path: str) -> str:
        """Estrae testo da PDF con pdftotext o PyMuPDF"""
        try:
            import subprocess
            result = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
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
            pass
        
        return "Impossibile estrarre testo dal PDF"
    
    def _extract_docx(self, path: str) -> str:
        """Estrae testo da DOCX"""
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(path) as z:
                xml_content = z.read('word/document.xml')
                root = ET.fromstring(xml_content)
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                texts = [t.text for t in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if t.text]
                return '\n'.join(texts)
        except:
            return "Impossibile estrarre testo dal DOCX"
    
    def search(self, query: str, limit=5, threshold=0.3) -> List[dict]:
        """Ricerca ibrida: FTS (keyword) + cosine similarity (semantica)"""
        with self._lock:
            c = self.db.cursor()
            query_emb = self._encode(query)
            
            # 1. FTS search
            safe_query = query.replace('"', '').replace("'", "''").replace('\\', '\\\\')
            words = [w for w in safe_query.split() if len(w) > 2]
            fts_query = ' OR '.join(f'"{w}"' for w in words) if words else f'"{safe_query}"'
            
            try:
                c.execute("""SELECT dc.id, dc.content, dc.embedding, d.title, d.source, d.metadata
                    FROM document_chunks dc
                    JOIN documents d ON dc.doc_id = d.id
                    JOIN chunks_fts f ON dc.id = f.rowid
                    WHERE chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?""", (fts_query, limit * 3))
            except:
                c.execute("""SELECT dc.id, dc.content, dc.embedding, d.title, d.source, d.metadata
                    FROM document_chunks dc
                    JOIN documents d ON dc.doc_id = d.id
                    LIMIT ?""", (limit * 3,))
            
            fts_results = [dict(r) for r in c.fetchall()]
            
            # 2. Semantic scoring con cosine similarity
            scored = []
            for r in fts_results:
                emb_json = r.get("embedding")
                if emb_json:
                    try:
                        chunk_emb = np.array(json.loads(emb_json), dtype=np.float32)
                        cosine_sim = float(np.dot(query_emb, chunk_emb))
                    except:
                        cosine_sim = self._keyword_score(r["content"], query)
                else:
                    cosine_sim = self._keyword_score(r["content"], query)
                
                keyword_score = self._keyword_score(r["content"], query)
                hybrid_score = 0.6 * cosine_sim + 0.4 * keyword_score
                
                if hybrid_score >= threshold:
                    r["score"] = round(hybrid_score, 4)
                    r["cosine"] = round(cosine_sim, 4)
                    r["keyword"] = round(keyword_score, 4)
                    scored.append(r)
            
            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[:limit]
    
    def _keyword_score(self, content: str, query: str) -> float:
        """Calcola score basato su keyword matching"""
        content_lower = content.lower()
        query_words = query.lower().split()
        matches = sum(1 for w in query_words if w in content_lower)
        base = matches / max(len(query_words), 1)
        return min(1.0, base)
    
    def semantic_search(self, query: str, limit=5) -> List[dict]:
        """Ricerca puramente semantica (solo cosine similarity su TUTTI i chunk)"""
        with self._lock:
            c = self.db.cursor()
            query_emb = self._encode(query)
            
            c.execute("""SELECT dc.id, dc.content, dc.embedding, d.title, d.source
                FROM document_chunks dc
                JOIN documents d ON dc.doc_id = d.id
                WHERE dc.embedding IS NOT NULL""")
            
            results = []
            for row in c.fetchall():
                r = dict(row)
                try:
                    chunk_emb = np.array(json.loads(r["embedding"]), dtype=np.float32)
                    sim = float(np.dot(query_emb, chunk_emb))
                except:
                    sim = 0
                if sim > 0.2:
                    r["score"] = round(sim, 4)
                    results.append(r)
            
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:limit]
    
    def query_context(self, query: str, max_chunks=5) -> str:
        """Cerca e restituisce contesto RAG formattato per prompt LLM"""
        results = self.search(query, limit=max_chunks)
        if not results or results[0].get("score", 0) < 0.3:
            return ""
        
        parts = ["CONTESTO DA DOCUMENTI (RAG):"]
        for i, r in enumerate(results, 1):
            parts.append(f"[{i}] Da «{r.get('title', '?')}»:")
            content = r["content"][:800]
            parts.append(content if len(r["content"]) <= 800 else content + "...")
        
        return "\n\n".join(parts)
    
    def list_documents(self, limit=50) -> List[dict]:
        """Lista tutti i documenti"""
        c = self.db.cursor()
        c.execute("""SELECT d.id, d.title, d.source, d.metadata, d.created_at,
            (SELECT COUNT(*) FROM document_chunks WHERE doc_id = d.id) as chunks
            FROM documents d ORDER BY d.created_at DESC LIMIT ?""", (limit,))
        return [dict(r) for r in c.fetchall()]
    
    def delete_document(self, doc_id: int) -> dict:
        """Elimina documento e i suoi chunk"""
        with self._lock:
            c = self.db.cursor()
            c.execute("DELETE FROM document_chunks WHERE doc_id=?", (doc_id,))
            c.execute("DELETE FROM documents WHERE id=?", (doc_id,))
            self.db.commit()
        return {"status": "ok", "deleted": doc_id}
    
    def delete_all(self) -> dict:
        """Elimina tutti i documenti"""
        with self._lock:
            c = self.db.cursor()
            c.execute("DELETE FROM document_chunks")
            c.execute("DELETE FROM documents")
            self.db.commit()
        return {"status": "ok", "message": "Tutti i documenti eliminati"}
    
    def stats(self) -> dict:
        """Statistiche RAG"""
        c = self.db.cursor()
        c.execute("SELECT COUNT(*) as total FROM documents")
        docs = c.fetchone()["total"]
        c.execute("SELECT COUNT(*) as total FROM document_chunks")
        chunks = c.fetchone()["total"]
        c.execute("SELECT COUNT(*) as total FROM document_chunks WHERE embedding IS NOT NULL AND embedding != ''")
        with_emb = c.fetchone()["total"]
        return {
            "documents": docs,
            "chunks": chunks,
            "embedded_chunks": with_emb,
            "model": self._model_name or "none (hash fallback)"
        }
    
    def _auto_embed_pending(self):
        """All'avvio, genera embedding per chunk che ne sono sprovvisti"""
        try:
            c = self.db.cursor()
            c.execute("""SELECT id, content FROM document_chunks
                WHERE embedding IS NULL OR embedding = '' LIMIT 100""")
            pending = [dict(r) for r in c.fetchall()]
            if pending:
                print(f"[RAG] Genero embedding per {len(pending)} chunk in sospeso...")
                for row in pending:
                    emb = self._encode(row["content"]).tolist()
                    c.execute("UPDATE document_chunks SET embedding=? WHERE id=?",
                              (json.dumps(emb), row["id"]))
                self.db.commit()
                print(f"[RAG] ✅ Embedded {len(pending)} chunk")
        except Exception as e:
            print(f"[RAG] Auto-embed: {e}")
    
    def close(self):
        self.db.close()

# Singleton
rag = JarvisRAG()
