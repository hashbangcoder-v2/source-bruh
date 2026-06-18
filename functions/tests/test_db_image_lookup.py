import sys
from pathlib import Path

from google.cloud.firestore_v1.vector import Vector


current_dir = Path(__file__).resolve()
sys.path.insert(0, str(current_dir.parents[1]))

from db import FirestoreDB


class FakeDoc:
    def __init__(self, exists=True):
        self.exists = exists

    def to_dict(self):
        return {"storage_path": "users/u1/images/img1/original"}


class FakeCollection:
    def __init__(self, calls):
        self.calls = calls

    def document(self, doc_id):
        self.calls.append(("document", doc_id))
        return self

    def collection(self, name):
        self.calls.append(("collection", name))
        return self

    def get(self):
        self.calls.append(("get",))
        return FakeDoc()


class FakeFirestore:
    def __init__(self):
        self.calls = []

    def collection(self, name):
        self.calls.append(("collection", name))
        if name != "users":
            raise AssertionError("root image collection should not be queried when user_id is provided")
        return FakeCollection(self.calls)


class FakeRef:
    def __init__(self):
        self.updates = []

    def update(self, payload):
        self.updates.append(payload)


class FakeBackfillDoc:
    def __init__(self, data):
        self._data = data
        self.reference = FakeRef()

    def to_dict(self):
        return self._data


def test_get_image_document_uses_user_collection_before_collection_group():
    db = FirestoreDB.__new__(FirestoreDB)
    db.db = FakeFirestore()
    db._use_firestore = True
    db._IMAGES_COLLECTION = "images"

    doc = db._get_image_document("img1", user_id="u1")

    assert doc["image_rowid"] == "img1"
    assert ("collection", "users") in db.db.calls
    assert ("document", "u1") in db.db.calls
    assert ("collection", "images") in db.db.calls
    assert ("document", "img1") in db.db.calls


def test_profile_stats_count_local_images_and_queries():
    db = FirestoreDB.__new__(FirestoreDB)
    db._use_firestore = False
    db._local_users = {}
    db._local_images = {
        "img1": {"user_id": "u1"},
        "img2": {"user_id": "u1"},
        "img3": {"user_id": "u2"},
    }

    db.record_query_event("u1", "brazil", 30, 4)
    db.record_query_event("u1", "oecd gdp", 30, 2)

    stats = db.get_profile_stats("u1")

    assert stats == {
        "files_indexed": 2,
        "queries_lifetime": 2,
        "queries_last_week": 2,
    }


def test_prepare_image_payload_adds_firestore_vector_field():
    db = FirestoreDB.__new__(FirestoreDB)
    db._vector_field = "embedding_vector"

    payload = db._prepare_image_payload({"embedding": [0.1, 0.2, 0.3]})

    assert payload["embedding"] == [0.1, 0.2, 0.3]
    assert isinstance(payload["embedding_vector"], Vector)
    assert FirestoreDB._coerce_embedding_list(payload["embedding_vector"]) == [0.1, 0.2, 0.3]


def test_search_prefers_firestore_vector_search():
    db = FirestoreDB.__new__(FirestoreDB)
    db._use_firestore = True
    db._vector_search_enabled = True
    db._vector_search_fallback = True
    calls = []

    def vector_search(user_id, query_embedding, top_k):
        calls.append(("vector", user_id, top_k))
        return [{"image_rowid": "img1", "distance": 0.12}]

    def full_scan(user_id, query_embedding, top_k):
        calls.append(("full_scan", user_id, top_k))
        return []

    db.search_vectors_firestore = vector_search
    db.search_vectors = full_scan

    results = db.search([0.1, 0.2], top_k=5, user_id="u1")

    assert results == [{"image_rowid": "img1", "distance": 0.12}]
    assert calls == [("vector", "u1", 5)]


def test_search_falls_back_when_vector_index_is_not_ready():
    db = FirestoreDB.__new__(FirestoreDB)
    db._use_firestore = True
    db._vector_search_enabled = True
    db._vector_search_fallback = True
    calls = []

    def vector_search(user_id, query_embedding, top_k):
        calls.append("vector")
        raise RuntimeError("missing vector index")

    def full_scan(user_id, query_embedding, top_k):
        calls.append("full_scan")
        return [{"image_rowid": "img1", "distance": 0.2}]

    db.search_vectors_firestore = vector_search
    db.search_vectors = full_scan

    results = db.search([0.1, 0.2], top_k=5, user_id="u1")

    assert results == [{"image_rowid": "img1", "distance": 0.2}]
    assert calls == ["vector", "full_scan"]


def test_backfill_embedding_vectors_updates_missing_vector_field():
    docs = [
        FakeBackfillDoc({"embedding": [0.1, 0.2]}),
        FakeBackfillDoc({"embedding": [0.3, 0.4], "embedding_vector": Vector([0.3, 0.4])}),
        FakeBackfillDoc({"description": "no embedding"}),
    ]

    class BackfillCollection:
        def stream(self):
            return iter(docs)

    db = FirestoreDB.__new__(FirestoreDB)
    db._vector_field = "embedding_vector"
    db._images_collection = lambda user_id: BackfillCollection()

    result = db.backfill_embedding_vectors("u1", dry_run=False)

    assert result == {
        "scanned": 3,
        "updated": 1,
        "skipped": 1,
        "missing_embedding": 1,
        "dry_run": 0,
    }
    assert isinstance(docs[0].reference.updates[0]["embedding_vector"], Vector)
    assert docs[1].reference.updates == []
