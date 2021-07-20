import os
import pickle
import utils
import preferences

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import BatchHttpRequest

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/contacts.readonly',
    'https://www.googleapis.com/auth/photoslibrary.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
]

def get_google_service(api, version):
    creds = None
    email = preferences.ChromePreferences().get_email()
    token_path = os.path.join(utils.HOME_DIR, 'google_token_%s.pickle' % email)
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('importers/gmail_credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
    return build(api, version, credentials=creds)


def batch(service, requests, callback):
    for chunk in chunks(requests, 100):
        batch = service.new_batch_http_request()
        for request in chunk:
            batch.add(request, callback=callback)
        batch.execute()


def chunks(elements, chunkSize):
    for n in range(0, len(elements), chunkSize):
        yield elements[n:n + chunkSize]