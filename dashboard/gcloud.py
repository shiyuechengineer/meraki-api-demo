import os

from google.auth import compute_engine
from google.cloud import firestore


PROJECT_ID = os.environ.get('PROJECT_ID')
COLLECTION_ID = os.environ.get('COLLECTION_ID')
SERVICE_ACCOUNT_FILE = os.environ.get('SERVICE_ACCOUNT_FILE')


def get_demos(db):
    coll_ref = db.collection(COLLECTION_ID)
    docs = coll_ref.stream()
    demos = [doc.to_dict() for doc in docs]
    return demos


def db_read(db, doc_id):
    coll_ref = db.collection(COLLECTION_ID)
    doc_ref = coll_ref.document(doc_id)
    doc = doc_ref.get()
    return doc.to_dict()


def db_write(db, doc_id, data):
    coll_ref = db.collection(COLLECTION_ID)
    doc_ref = coll_ref.document(doc_id)
    doc_ref.update(data)


def gcloud_db():
    credentials = compute_engine.Credentials()
    db = firestore.Client(credentials=credentials, project=PROJECT_ID)
    return db
