import os
import json
import hashlib
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Tuple

import sqlite_vec


class Database:
    def __init__(self, db_path: str, vector_dimension: int) -> None:
        self.db_path = db_path
        self.vector_dimension = vector_dimension
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._initialize_extensions()
        self._initialize_schema()

    def _initialize_extensions(self) -> None:
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)

    def _initialize_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                google_media_id TEXT UNIQUE,
                album_title TEXT,
                file_path TEXT NOT NULL,
                thumb_path TEXT,
                timestamp TEXT,
                width INTEGER,
                height INTEGER,
                sha256 TEXT,
                description TEXT,
                ocr_text TEXT,
                tags TEXT
            )
            """
        )
        # Virtual table for vectors
        cur.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS vectors USING vec0(
                embedding FLOAT[{self.vector_dimension}],
                image_rowid INTEGER
            )
            """
        )
        # Helpful indices
        cur.execute("CREATE INDEX IF NOT EXISTS idx_images_media_id ON images(google_media_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_images_sha256 ON images(sha256)")
        # Note: sqlite-vec virtual tables cannot be indexed; skip index on vectors
        self.conn.commit()

    def compute_sha256(self, data: bytes) -> str:
        h = hashlib.sha256()
        h.update(data)
        return h.hexdigest()

    def upsert_image(
        self,
        *,
        google_media_id: Optional[str],
        album_title: Optional[str],
        file_path: str,
        thumb_path: Optional[str],
        timestamp: Optional[str],
        width: Optional[int],
        height: Optional[int],
        sha256: Optional[str],
        description: Optional[str],
        ocr_text: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None,
    ) -> int:
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO images (google_media_id, album_title, file_path, thumb_path, timestamp, width, height, sha256, description, ocr_text, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(google_media_id) DO UPDATE SET
                album_title=excluded.album_title,
                file_path=excluded.file_path,
                thumb_path=excluded.thumb_path,
                timestamp=excluded.timestamp,
                width=excluded.width,
                height=excluded.height,
                sha256=excluded.sha256,
                description=excluded.description,
                ocr_text=excluded.ocr_text,
                tags=excluded.tags
            """,
            (
                google_media_id,
                album_title,
                file_path,
                thumb_path,
                timestamp,
                width,
                height,
                sha256,
                description,
                ocr_text,
                json.dumps(tags) if isinstance(tags, dict) else tags,
            ),
        )
        self.conn.commit()
        # Retrieve rowid (Rowid of existing or just inserted)
        if google_media_id is not None:
            row = cur.execute(
                "SELECT rowid FROM images WHERE google_media_id = ?",
                (google_media_id,),
            ).fetchone()
            return int(row[0])
        row = cur.execute(
            "SELECT rowid FROM images WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        return int(row[0])

    def insert_or_replace_vector(self, image_rowid: int, embedding: List[float]) -> None:
        cur = self.conn.cursor()
        # Remove existing vector for this image_rowid if present
        cur.execute("DELETE FROM vectors WHERE image_rowid = ?", (image_rowid,))
        cur.execute(
            "INSERT INTO vectors (embedding, image_rowid) VALUES (?, ?)",
            (json.dumps(embedding), image_rowid),
        )
        self.conn.commit()

    def has_image_by_media_id(self, google_media_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM images WHERE google_media_id = ?",
            (google_media_id,),
        ).fetchone()
        return row is not None

    def search(self, query_embedding: List[float], top_k: int = 20) -> List[sqlite3.Row]:
        # sqlite-vec MATCH expects a JSON array string or a blob vector; we pass JSON
        query_json = json.dumps(query_embedding)
        rows = self.conn.execute(
            """
            SELECT i.rowid AS image_rowid, i.google_media_id, i.album_title, i.file_path, i.thumb_path,
                   i.timestamp, i.width, i.height, i.description,
                   v.distance
            FROM vectors v
            JOIN images i ON i.rowid = v.image_rowid
            WHERE v.embedding MATCH ?
            ORDER BY v.distance
            LIMIT ?
            """,
            (query_json, top_k),
        ).fetchall()
        return rows

    def get_image_paths(self, image_rowid: int) -> Tuple[str, Optional[str]]:
        row = self.conn.execute(
            "SELECT file_path, thumb_path FROM images WHERE rowid = ?",
            (image_rowid,),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(f"Image with rowid {image_rowid} not found")
        return str(row[0]), str(row[1]) if row[1] is not None else None

    def close(self) -> None:
        self.conn.close()


