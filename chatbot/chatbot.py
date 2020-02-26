from datetime import datetime
from datetime import timedelta
import time

from requests_toolbelt.multipart.encoder import MultipartEncoder


# Get the event (most recent message) that triggered the webhook
def get_message(session, event, headers):
    url = f'https://api.ciscospark.com/v1/messages/{event["data"]["id"]}'
    response = session.get(url, headers=headers)
    return response.json()['text']


# Get person (both name and email)
def get_person(session, user_id, headers, retries=5, name=None):
    url = f'https://api.ciscospark.com/v1/people/{user_id}'
    while retries > 0:
        response = session.get(url, headers=headers)
        if response.ok:
            data = response.json()
            if name and name == 'first':
                full_name = data['displayName']
                first_name = full_name.split()[0]
                n = first_name
            elif name and name == 'last':
                full_name = data['displayName']
                last_name = full_name.split()[-1]
                n = last_name
            elif data['displayName']:
                n = data['displayName']
            else:
                n = f'{data["firstName"]} {data["lastName"]}'
            emails = data['emails']
            return (n, emails)
        elif response.status_code == 429:
            wait = int(response.headers['Retry-After'])
            time.sleep(wait)
            print(f'429 encountered, so waiting {wait} seconds')
            retries -= 1
    return (None, None)


# Get user's info
def get_user(session, user_id, headers):
    url = f'https://api.ciscospark.com/v1/people/{user_id}'
    response = session.get(url, headers=headers)
    return response.json()


# Get user's name
def get_name(session, user_id, headers, name=None):
    data = get_user(session, user_id, headers)
    if data['displayName']:
        if name and name == 'first':
            full_name = data['displayName']
            first_name = full_name.split()[0]
            return first_name
        elif name and name == 'last':
            full_name = data['displayName']
            last_name = full_name.split()[-1]
            return last_name
        else:
            return data['displayName']
    else:
        return f'{data["firstName"]} {data["lastName"]}'


# Get user's emails
def get_emails(session, user_id, headers):
    data = get_user(session, user_id, headers)
    return data['emails']


# Get chatbot's own ID
def get_chatbot_id(session, headers):
    response = session.get('https://api.ciscospark.com/v1/people/me', headers=headers)
    return response.json()['id']


# Get chatbot's rooms
def get_chatbot_rooms(session, headers):
    response = session.get('https://api.ciscospark.com/v1/rooms', headers=headers)
    return response.json()


# Get room ID for desired space
def get_room_id(session, headers, room_name):
    rooms = get_chatbot_rooms(session, headers)
    for room in rooms:
        if room['title'] == room_name:
            return room['id']
    return None


# Get card submission data
def get_card_data(session, headers, action_id):
    response = session.get(f'https://api.ciscospark.com/v1/attachment/actions/{action_id}', headers=headers)
    return response.json()['inputs']


# Send a message in Webex Teams
def post_message(session, headers, payload, message, thread=None):
    if thread:
        payload['parentId'] = thread
    payload['markdown'] = message
    session.post('https://api.ciscospark.com/v1/messages/',
                 headers=headers,
                 json=payload)


# Send a message with file attachment in Webex Teams
def post_file(session, headers, payload, message, file_url):
    payload['file'] = file_url
    post_message(session, headers, payload, message)


# Send a message with file attached from local storage
def send_file(session, headers, payload, message, file_path, file_type='text/plain'):
    payload['markdown'] = message
    payload['files'] = (file_path, open(file_path, 'rb'), file_type)
    m = MultipartEncoder(payload)
    session.post('https://api.ciscospark.com/v1/messages', data=m,
                      headers={'Authorization': headers['authorization'],
                               'Content-Type': m.content_type})


# Download file from URL and write to local tmp storage
def download_file(session, file_name, file_url):
    attempts = 1
    while attempts <= 30:
        r = session.get(file_url, stream=True)
        if r.ok:
            print(f'Retried {attempts} times until successfully retrieved {file_url}')
            temp_file = f'/tmp/{file_name}.jpg'
            with open(temp_file, 'wb') as f:
                for chunk in r:
                    f.write(chunk)
            return temp_file
        else:
            attempts += 1
    print(f'Unsuccessful in 30 attempts retrieving {file_url}')
    return None


# Function to check whether message begins with one of multiple possible options
def message_begins(text, options):
    message = text.strip().lower()
    for option in options:
        if message.startswith(option):
            return True
    return False


# Function to check whether message contains one of multiple possible options
def message_contains(text, options):
    message = text.strip().lower()
    for option in options:
        if option in message:
            return True
    return False


# Clear your screen and display Miles!
def clear_screen(session, headers, payload):
    post_message(session, headers, payload,
                 '''```
                                   ./(((((((((((((((((/.
                             *(((((((((((((((((((((((((((((
                         .(((((((((((((((((((((((((((((((((((/
                       ((((((((((((((((((((((((((((((((((((((((/
                    ,((((((((((((((((((((((((((((((((((((((((((((
                  .((((((((((((((((((((     ((((((/     ((((((((((,
                 ((((((((((((((((((((((     ((((((/     (((((((((((
               /((((((((((((((((((((((((((((((((((((((((((((((((((((
              ((((((((((((((((((((((((((((((((((((((((((((((((((((((*
             ((((((((((((((((((((((((((((((((((((((((((((((((((((((((
            (((((((((((((((((((((((((((((((((((((((((((((((((((((((((
           ((((((((((((((((((((((((     ((((((((((((((/     (((((((((
          ,((((((((((((((((((((((((     ((((((((((((((/     ((((((((/
          (((((((((((((((((((((((((    .//////////////*    .((((((((
         ,(((((((((((((((((((((((((((((/              ((((((((((((.
         ((((((((((((((((((((((((((((((/              (((((((((((
         (((((((((((((((((((((((((((((((((((((((((((((((((((((((*
        .(((((((((((((((((((((((((((((((((((((((((((((((((((((*
        /((((((((((((((((((((((((((((((((((((((((((((((((((*
        (((((((((((((((((((((((((((((((((((((((((((((((*
        (((((((((((/.                     ....
        (((((((/
        (((((
        (((
        /.
    ''')


# List direct rooms (https://developer.webex.com/docs/api/v1/rooms/list-rooms)
def list_rooms(session, headers):
    url = 'https://api.ciscospark.com/v1/rooms?type=direct'
    response = session.get(url, headers=headers)
    return response.json()['items']


# List messages for room (https://developer.webex.com/docs/api/v1/messages/list-messages)
def list_messages(session, headers, room_id):
    url = f'https://api.ciscospark.com/v1/messages?roomId={room_id}'
    response = session.get(url, headers=headers)
    return response.json()['items']


# Function to prevent duplicating messages if matching snippet for user's email and within lookback time in minutes
def already_duplicated(session, headers, snippet, email, lookback):
    # Get current time
    now = datetime.utcnow()

    # Get list of rooms for chatbot, and then find user's room
    rooms = list_rooms(session, headers)
    for room in rooms:
        user_id = room['creatorId']
        if email in get_emails(session, user_id, headers):
            break

    # Get list of messages in that room
    messages = list_messages(session, headers, room['id'])

    # Filter on messages that match
    match_snippet = [m for m in messages if 'webex.bot' in m['personEmail'] and m['markdown'] == snippet]

    # See if any matched messages are within last lookback minutes
    if match_snippet:
        earlier = now - timedelta(minutes=lookback)
        matches = [m for m in match_snippet if earlier < datetime.strptime(m['created'], '%Y-%m-%dT%H:%M:%S.%fZ')]
        if matches:
            return True
    else:
        return False


# Delete room
def del_room(session, room_id, headers):
    url = f'https://api.ciscospark.com/v1/rooms/{room_id}'
    response = session.delete(url, headers=headers)


# Add user to room
def add_user(session, email, room_id, headers):
    url = f'https://api.ciscospark.com/v1/memberships/'
    data = {'personEmail': email, 'roomId': room_id}
    response = session.post(url, json=data, headers=headers)
