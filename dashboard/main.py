from datetime import datetime
import json
import os
import sys

import requests

from chatbot import *
from gcloud import *
from snapshot import *


BOT_TOKEN = os.environ.get('BOT_TOKEN')


# Main handler function
def handler(request):
    # Webhook event/metadata received, so now retrieve the actual message for the event
    webhook_event = request.get_json()
    print(webhook_event)

    # Look up org ID and associated Webex Teams room
    org_id = webhook_event['organizationId']
    db = gcloud_db()
    demos = get_demos(db)
    demo_orgs = [d for d in demos if 'org_id' in d]
    demo_ids = [d['org_id'] for d in demo_orgs]
    if org_id not in demo_ids:
        return ('Dashboard organization not found in any demos', 403, {'Access-Control-Allow-Origin': '*'})
    demo = demo_orgs[demo_ids.index(org_id)]
    api_key = demo['api_key']
    room_id = demo['room_id']

    # Do not continue if shared secret does not match
    if 'API demo' != webhook_event['sharedSecret']:
        # Except for "send test webhook" button
        if not (not webhook_event['alertId'] and not webhook_event['alertData']):
            return ('incorrect shared secret', 403, {'Access-Control-Allow-Origin': '*'})

    # Parse event data
    alert = webhook_event['alertType']
    data = webhook_event['alertData']
    name = data['name'] if 'name' in data else ''
    network = webhook_event['networkName']
    network = network.replace('@', '')  # @ sign messes up markdown
    network_link = webhook_event['networkUrl']
    device = webhook_event['deviceName'] if 'deviceName' in webhook_event else ''
    if device:
        device_link = webhook_event['deviceUrl']

    # Compose and format message to user
    session = requests.Session()
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {BOT_TOKEN}'
    }
    payload = {'roomId': room_id}
    message = f'**{alert}**'
    if alert == 'Motion detected':
        # Format motion alert message with link to camera
        net_id = webhook_event['networkId']
        serial = webhook_event['deviceSerial']
        time_zone = get_network(api_key, net_id, session)['timeZone']
        timestamp = datetime.utcfromtimestamp(data['timestamp'])    # UTC
        utc_time = pytz.utc.localize(timestamp)
        local_time = utc_time.astimezone(pytz.timezone(time_zone))
        file_name = device + ' - ' + local_time.strftime('%Y-%m-%d_%H-%M-%S')
        video = get_video_link(api_key, net_id, serial, timestamp=str(data['timestamp']).replace('.', ''), session=session)
        message += f' - [{network}]({network_link})'
        message += f': _[{device}]({video})_'
    else:
        if name:
            message += f' - _{name}_'
        message += f': [{network}]({network_link})'
        if device:
            message += f' - _[{device}]({device_link})_'

    # Prevent the same message from being sent repeatedly in the lookback timeframe
    # if already_duplicated(session, headers, message, user_email, lookback):
    #     message = 'MUTED!! ' + message
    #     print(message)

    # Include snapshot for motion detections
    if alert == 'Motion detected':
        if 'imageUrl' in data and data['imageUrl']:  # use motion recap image if available
            file_url = data['imageUrl']
        else:   # use timestamp from webhook alert
            file_url = generate_snapshot(api_key, net_id, serial, utc_time.isoformat(), session)

        if file_url:    # download/GET image from URL
            temp_file = download_file(session, file_name, file_url)
            if temp_file:
                send_file(session, headers, payload, message, temp_file, file_type='image/jpg')
            else:
                # If snapshot failed due to timestamp being more recent than cache, take a snapshot right now
                file_url = generate_snapshot(api_key, net_id, serial, session=session)
                if file_url:
                    temp_file = download_file(session, file_name, file_url)
                    if temp_file:
                        send_file(session, headers, payload, message, temp_file, file_type='image/jpg')
                    else:
                        message += ' (snapshot unsuccessfully retrieved)'
                        post_message(session, headers, payload, message)
                else:
                    message += ' (snapshot unsuccessfully requested)'
                    post_message(session, headers, payload, message)
        else:
            message += ' (snapshot unsuccessfully requested)'
            post_message(session, headers, payload, message)

    # Add more alert information and format JSON
    elif data:
        message += f'  \n```{json.dumps(data, indent=2, sort_keys=True)}'[:-1]  # screwy Webex Teams formatting
        post_message(session, headers, payload, message)

    # Send the webhook without alert data
    elif message != '':
        post_message(session, headers, payload, message)

    # Set CORS headers for the main request; let Meraki know success
    return ('webhook received', 200, {'Access-Control-Allow-Origin': '*'})
