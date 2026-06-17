import sys
from pathlib import Path


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
