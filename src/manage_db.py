import sqlite3
import sqlite_vec
import numpy as np
import datetime
from typing import List, Tuple
import requests

class SQLiteManager:
    def __init__(self, db_name="vector_database.db"):
        # Initialize the SQLite database connection
        self.conn = sqlite3.connect(db_name)
        # Enable and load the sqlite-vec extension
        self.conn.enable_load_extension(True)
        sqlite_vec.load(self.conn)
        self.conn.enable_load_extension(False)
        self.cursor = self.conn.cursor()
        # Create the vectors table if it doesn't exist
        self._create_table()

    def _create_table(self):
        # Create a virtual table for storing vector embeddings and metadata
        self.cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vectors USING vec0(
                embedding FLOAT[512],  # Store vector embeddings as 512-dimensional arrays
                timestamp TEXT NOT NULL,  # Record timestamp for each entry
                user_email TEXT NOT NULL,  # Email associated with the embedding
                description TEXT NOT NULL  # Text description of the entry
            );
        """)
        self.conn.commit()

    def _calculate_embedding(self, image_path: str) -> np.ndarray:
        """Fetches embedding for an image using an external API."""
        url = "https://api.example.com/embedding"  # Replace with your API endpoint
        files = {"file": open(image_path, "rb")}
        response = requests.post(url, files=files)
        response.raise_for_status()
        # Convert API response into a numpy array
        return np.array(response.json()["embedding"], dtype=np.float32)

    def add_records(self, image_paths: List[str], user_email: str, descriptions: List[str]):
        """Adds records of image embeddings and metadata to the database."""
        if len(image_paths) != len(descriptions):
            raise ValueError("Each image must have a corresponding description.")

        with self.conn:
            for image_path, description in zip(image_paths, descriptions):
                # Calculate embedding for the image
                embedding = self._calculate_embedding(image_path)
                # Directly store the embedding as FLOAT array in the database
                timestamp = datetime.datetime.now().isoformat()
                # Insert the record into the database
                self.cursor.execute(
                    "INSERT INTO vectors (embedding, timestamp, user_email, description) VALUES (?, ?, ?, ?)",
                    (embedding.tolist(), timestamp, user_email, description)
                )

    def search_similar(self, query_embedding: np.ndarray, top_k: int) -> List[Tuple[int, str, str, str, float]]:
        """Searches for the top-k similar embeddings in the database."""
        rows = self.cursor.execute(
            """
            SELECT rowid, timestamp, user_email, description, distance
            FROM vectors
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
            """,
            (query_embedding.tolist(), top_k)
        ).fetchall()
        return rows

    def delete_record(self, record_id: int):
        """Deletes a record from the database based on its row ID."""
        self.cursor.execute("DELETE FROM vectors WHERE rowid = ?", (record_id,))
        self.conn.commit()

    def close(self):
        """Closes the database connection."""
        self.conn.close()

# Example Usage
if __name__ == "__main__":
    manager = SQLiteManager()

    # Adding records
    manager.add_records(
        image_paths=["image1.jpg", "image2.jpg"],
        user_email="user@example.com",
        descriptions=["Sample description 1", "Sample description 2"]
    )

    # Searching for similar embeddings
    query = np.random.rand(512).astype(np.float32)  # Replace with actual query embedding
    top_results = manager.search_similar(query, top_k=5)
    print("Top results:", top_results)

    # Deleting a record
    manager.delete_record(record_id=1)

    # Closing the database connection
    manager.close()
