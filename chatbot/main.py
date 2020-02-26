import os
import sys

import requests

from card import *
from chatbot import *
from gcloud import *


# Main handler function
def handler(request):
    # Set CORS headers for the main request
    return_headers = {
        'Access-Control-Allow-Origin': '*'
    }

    # Webhook event/metadata received, so now retrieve the actual message for the event
    webhook_event = request.get_json()
    data = webhook_event['data']
    room_id = data['roomId']
    print(webhook_event)

    # Lookup the room & associated demo
    session = requests.Session()
    db = gcloud_db()
    user_id = webhook_event['actorId']
    demos = get_demos(db)
    demo_rooms = [d['room_id'] for d in demos if 'room_id' in d]
    bot_email = BOT_EMAIL
    bot_token = BOT_TOKEN
    headers = {
        'content-type': 'application/json; charset=utf-8',
        'authorization': f'Bearer {bot_token}'
    }
    payload = {'roomId': room_id}

    # Ignore bot's own actions
    if webhook_event['resource'] == 'messages' and data['personEmail'] == bot_email:
        return ('', 200, return_headers)

    # Process card submission
    if webhook_event['resource'] == 'attachmentActions' and 'type' in data and data['type'] == 'submit':
        inputs = get_card_data(session, headers, data['id'])
        payload['parentId'] = data['messageId']
        if inputs['myCardIndex'] == 'start':
            card_start(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'welcome':
            card_welcome(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'input_key':
            card_input_key(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'org_select':
            card_org_select(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'org_create':
            card_org_create(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'main_menu':
            card_main_menu(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'new_site':
            card_new_site(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'wifi_psk':
            card_wifi_psk(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'loss_latency':
            wan_health(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'change_logo':
            change_logo(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'shut_down' or inputs['myCardIndex'] == 'shut_down_org':
            shut_down(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'webhook_alerts':
            webhook_alerts(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'add_users':
            card_add_users(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'get_clients':
            get_clients(session, headers, payload, data, inputs, db)
        elif inputs['myCardIndex'] == 'reset_demo':
            inputs = {'opt_shut': 'Yes', 'opt_org': 'true'}
            shut_down(session, headers, payload, data, inputs, db)
        room_id = payload['roomId']
        counter = db_read(db, room_id)['usage_counter']
        db_write(db, room_id, {'usage_counter': counter + 1})
        return ('', 200, return_headers)

    # Tell user to use demo room if messaged directly
    if room_id not in demo_rooms:
        (first_name, user_emails) = get_person(session, user_id, headers, name='first')
        user_rooms = [d['cu_name'] for d in demos if 'room_id' in d and set(user_emails).intersection(set(d['users']))]
        if len(user_rooms) == 1:
            post_message(session, headers, payload,
                         f'Hi **{first_name}**, please use the _{user_rooms[0]} API demo_ room instead!️')
        elif user_rooms:
            markdown = f'Hi **{first_name}**, please use one of the rooms you\'re in already!'
            user_rooms.sort()
            for room in user_rooms:
                markdown += f'\n  * _{room} API demo_'
            post_message(session, headers, payload, markdown)
        else:
            display_card(session, headers, payload, db, '99_api_demo.json')
        return ('', 200, return_headers)

    # Process message sent from demo room
    else:
        message = get_message(session, webhook_event, headers)

        # New site
        if message_contains(message, ['provision', 'create', 'deploy', 'site']):
            display_card(session, headers, payload, db, '10_new_site.json')
        # Wi-Fi PSK
        elif message_contains(message, ['wireless', 'password', 'psk', 'wi-fi', 'wifi']):
            display_card(session, headers, payload, db, '11_wifi_psk.json')
        # ISP health
        elif message_contains(message, ['isp', 'health', 'packet', 'loss', 'latency']):
            display_card(session, headers, payload, db, '20_loss_latency.json')
        # Devices
        elif message_contains(message, ['device', 'status', 'online']):
            device_statuses(session, headers, payload, data, None, db)
        # Snapshots
        elif message_contains(message, ['cam', 'photo', 'screen', 'snap', 'shot']):
            get_snapshots(session, headers, payload, data, None, db)
        # Clients
        elif message_contains(message, ['client', 'usage']):
            display_card(session, headers, payload, db, '30_get_clients.json')
        # Clear screen to reset demos
        elif message_contains(message, ['clear']):
            clear_screen(session, headers, payload)
        # Show main meu
        else:
            display_card(session, headers, payload, db, '04_main_menu.json')
        room_id = payload['roomId']
        counter = db_read(db, room_id)['usage_counter']
        db_write(db, room_id, {'usage_counter': counter + 1})

        # Let chat app know success
        return ('message received', 200, return_headers)
