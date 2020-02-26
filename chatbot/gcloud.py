from datetime import datetime
import os

from google.auth import compute_engine
from google.auth.transport.requests import AuthorizedSession
from google.cloud import firestore
from google.cloud import storage
from google.oauth2 import service_account


PROJECT_ID = os.environ.get('PROJECT_ID')
API_KEY = os.environ.get('API_KEY')
SCOPES = os.environ.get('SCOPES')
SERVICE_ACCOUNT_FILE = os.environ.get('SERVICE_ACCOUNT_FILE')
BUCKET_ID = os.environ.get('BUCKET_ID')
SEARCH_ID = os.environ.get('SEARCH_ID')
NAMESPACE = os.environ.get('NAMESPACE')


def get_demos(db):
    coll_ref = db.collection(BUCKET_ID)
    docs = coll_ref.stream()
    demos = [doc.to_dict() for doc in docs]
    return demos


def del_demo(db, doc_id):
    coll_ref = db.collection(BUCKET_ID)
    doc_ref = coll_ref.document(doc_id)
    doc_ref.update({u'api_key': firestore.DELETE_FIELD})
    doc_ref.update({u'room_id': firestore.DELETE_FIELD})
    doc_ref.update({u'web_url': firestore.DELETE_FIELD})
    doc_ref.update({u'virtual_serials': firestore.DELETE_FIELD})
    time_stamp = f'{datetime.now():%Y-%m-%d_%H-%M-%S}'
    db_write(db, doc_id, {u'deleted_at': time_stamp})


def db_read(db, doc_id):
    coll_ref = db.collection(BUCKET_ID)
    doc_ref = coll_ref.document(doc_id)
    doc = doc_ref.get()
    return doc.to_dict()


def db_write(db, doc_id, data):
    coll_ref = db.collection(BUCKET_ID)
    doc_ref = coll_ref.document(doc_id)
    doc_ref.update(data)


def gcloud_session():
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES.split(','))
    authed_session = AuthorizedSession(credentials)
    return authed_session


def gcloud_db():
    # credentials = compute_engine.Credentials()
    credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES.split(','))
    db = firestore.Client(credentials=credentials, project=PROJECT_ID)
    return db


def list_functions(session):
    url = f'https://cloudfunctions.googleapis.com/v1/projects/{PROJECT_ID}/locations/-/functions'
    response = session.get(url)
    if response.ok:
        return response.json()
    else:
        return None


# Function to search Google for images
def find_logo(session, name):
    if name.lower() == 'cisco meraki':
        link = 'https://meraki.cisco.com/img/cisco-meraki-og-logo.jpg'
        response = session.get(link)
        if response.ok:
            return link

    params = {
        'cx': SEARCH_ID,
        'q': f'{name} filetype:jpg',
        'key': API_KEY,
        'imgSize': 'large',
        'searchType': 'image',
    }
    response = session.get('https://www.googleapis.com/customsearch/v1', params=params)
    if response.ok:
        results = response.json()['items']
        for r in results:
            link = r['link']
            try:
                session.get(link, timeout=3)
            except:
                pass
            else:
                return link
        link = 'https://www.pngitem.com/pimgs/m/87-879176_cisco-webex-teams-hd-png-download.png'
        return link
    else:
        # Webex Teams icon
        link = 'https://www.pngitem.com/pimgs/m/87-879176_cisco-webex-teams-hd-png-download.png'
        return link


def upload_file(file):
    client = storage.Client.from_service_account_json(SERVICE_ACCOUNT_FILE)
    bucket = client.get_bucket(BUCKET_ID)
    blob = storage.Blob('Archive.zip', bucket)
    with open('chatbot/Archive.zip', 'rb') as fp:
        blob.upload_from_file(fp)


def list_services(session):
    url = f'https://us-east4-run.googleapis.com/apis/serving.knative.dev/v1/namespaces/{PROJECT_ID}/services'
    response = session.get(url)
    if response.ok:
        return response.json()
    else:
        return None


def create_service(session, name, api_key, org_id, logo_url):
    url = f'https://us-east4-run.googleapis.com/apis/serving.knative.dev/v1/namespaces/{PROJECT_ID}/services'
    data = {
        'apiVersion': 'serving.knative.dev/v1',
        'kind': 'Service',
        'metadata': {
            'name': name,
            'namespace': NAMESPACE,
            'labels': {'cloud.googleapis.com/location': 'us-east4'},
            'annotations': {
                'run.googleapis.com/client-name': 'gcloud',
                'serving.knative.dev/creator': 'shiychen@cisco.com',
                'serving.knative.dev/lastModifier': 'shiychen@cisco.com',
                'client.knative.dev/user-image': f'gcr.io/{PROJECT_ID}/web_ui',
                'run.googleapis.com/client-version': '280.0.0'
            },
        },
        'spec': {
            'template': {
                'spec': {
                    'containerConcurrency': 80,
                    'timeoutSeconds': 900,
                    'containers': [
                        {
                            'image': f'gcr.io/{PROJECT_ID}/web_ui',
                            'resources': {'limits': {'cpu': '1000m', 'memory': '2048M'}},
                            'ports': [{'containerPort': 8080}],
                            'env': [
                                {
                                    'name': 'API_KEY',
                                    'value': api_key
                                },
                                {
                                    'name': 'ORG_ID',
                                    'value': org_id
                                },
                                {
                                    'name': 'LOGO_URL',
                                    'value': logo_url
                                }
                            ]
                        }
                    ]
                }
            },
            'traffic': [{'percent': 100, 'latestRevision': True}]
        }
    }
    response1 = session.post(url, json=data)

    if response1.ok:
        url = f'https://us-east4-run.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-east4/services/{name}:setIamPolicy'
        data = {
            'policy': {
                'bindings': [
                    {
                        'role': 'roles/run.invoker',
                        'members': [
                            'allUsers'
                        ]
                    }
                ]
            }
        }
        response2 = session.post(url, json=data)
    if response2.ok:
        return response1.json()
    return None


def del_service(session, service_id):
    url = f'https://us-east4-run.googleapis.com/apis/serving.knative.dev/v1/namespaces/{PROJECT_ID}/services/{service_id}'
    session.delete(url)


def get_allocations(db):
    users_ref = db.collection(u'user-data')
    docs = users_ref.stream()
    user_allocations = [doc.to_dict()['allocation'] for doc in docs if 'allocation' in doc.to_dict()]

    coll_ref = db.collection(BUCKET_ID)
    docs = coll_ref.stream()
    demo_allocations = [doc.to_dict()['virtual_serials'] for doc in docs if 'virtual_serials' in doc.to_dict()]
    demo_allocations.extend(user_allocations)
    return demo_allocations
