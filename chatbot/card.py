from datetime import datetime
import json
import random
import re
import string
import time

from google.auth import compute_engine
from google.cloud import firestore
import matplotlib
matplotlib.use
import matplotlib.pyplot as plt
import pandas
import plivo
import pytz

from chatbot import *
from cv_gcp import *
from gcloud import *
import meraki
import pystache


SANDBOX_KEY = os.environ.get('SANDBOX_KEY')
SANDBOX_ORG = os.environ.get('SANDBOX_ORG')
MERAKI_DEMO_API_KEY = os.environ.get('MERAKI_DEMO_API_KEY')
RUN_DOMAIN = os.environ.get('RUN_DOMAIN')
BOT_TOKEN = os.environ.get('BOT_TOKEN')
BOT_EMAIL = os.environ.get('BOT_EMAIL')
PLIVO_AUTH_ID = os.environ.get('PLIVO_AUTH_ID')
PLIVO_AUTH_TOKEN = os.environ.get('PLIVO_AUTH_TOKEN')
PLIVO_PHONE_NUMBER = os.environ.get('PLIVO_PHONE_NUMBER')


# Display card in Webex Teams with data
def display_card(session, headers, payload, db, card_file, template=None):
    room_id = payload['roomId']
    demo = db_read(db, room_id)
    with open(f'cards/{card_file}') as fp:
        text = fp.read()
    if template:
        if demo:
            for k, v in template.items():
                demo[k] = json.dumps(v)
        else:
            demo = template
    converted = pystache.render(text, demo)
    card = json.loads(converted)
    data = {
        'roomId': room_id,
        'markdown': 'To run this API demo, view this message in a supported [Webex Teams](https://www.webex.com/downloads.html) client.',
        'attachments': [
            {'contentType': 'application/vnd.microsoft.card.adaptive', 'content': card}
        ]
    }
    response = session.post('https://api.ciscospark.com/v1/messages', headers=headers, json=data)
    print(response.status_code, response.text)
    return response


# Deploy web app/UI as a service
def web_ui(session, headers, payload, db):
    room_id = payload['roomId']
    demo = db_read(db, room_id)
    gsession = gcloud_session()

    # Deploy web app
    if 'web_url' not in demo:
        cu_name = demo['cu_name']
        gsession = gcloud_session()
        letters = string.ascii_lowercase
        hash = ''.join(random.choice(letters) for i in range(20))
        name = cu_name.lower().replace(' ', '-') + f'-{hash}'
        create_service(gsession, name, demo['api_key'], demo['org_id'], demo['logo_url'])
        url = f'https://{name}{RUN_DOMAIN}'
        db_write(db, payload['roomId'], {u'web_url': url})
        post_message(session, headers, payload,
                     f'Your provisioning [web app]({url}) is being deployed and will be ready in a minute or two. ⏱ Please undeploy after demoing this alternative UI via a webpage.')
    # Undeploy web app
    else:
        url = demo['web_url']
        service = demo['web_url'][8:].split(RUN_DOMAIN)[0]
        del_service(gsession, service)
        db_write(db, payload['roomId'], {u'web_url': firestore.DELETE_FIELD})
        post_message(session, headers, payload,
                     f'Your provisioning web app is now no longer deployed.')


# Start API demo
def card_start(session, headers, payload, data, inputs, db):
    bot_token = BOT_TOKEN

    cu_name = inputs['customer_name']
    cu_name = re.sub(r'[^A-Za-z0-9 ]+', '', cu_name)
    if not cu_name:
        cu_name = 'Cisco Meraki'
    logo_url = find_logo(session, cu_name)
    time_stamp = f'{datetime.now():%Y-%m-%d_%H-%M-%S}'

    # Create a new room
    new_headers = {'content-type': 'application/json; charset=utf-8', 'authorization': f'Bearer {bot_token}'}
    new_payload = {'title': f'{cu_name} API demo'}
    response = session.post('https://api.ciscospark.com/v1/rooms/', headers=new_headers, json=new_payload)

    # Add users to room
    room_id = response.json()['id']
    (user_name, user_emails) = get_person(session, data['personId'], headers)
    for address in user_emails:
        new_payload = {'roomId': room_id, 'personEmail': address}
        response = session.post('https://api.ciscospark.com/v1/memberships/', headers=new_headers, json=new_payload)

    # Send welcome message
    template = {'cu_name': cu_name, 'logo_url': logo_url, 'user_name': user_name}
    display_card(session, headers, new_payload, db, '00_welcome.json', template)

    # Store data to Firestore
    credentials = compute_engine.Credentials()
    db = firestore.Client(credentials=credentials, project=PROJECT_ID)
    col_ref = db.collection(u'api-demo')
    doc_ref = col_ref.document(room_id)
    data = {
        u'room_id': room_id,
        u'users': user_emails,
        u'created_at': time_stamp,
        u'cu_name': cu_name,
        u'logo_url': logo_url,
        u'usage_counter': 0,
    }
    doc_ref.set(data)

    time.sleep(3)
    post_message(session, headers, payload,
                 f'Your on-demand demo has been deployed ✅️, so please head over to the **{cu_name} API demo** room here in Webex Teams!')


def card_welcome(session, headers, payload, data, inputs, db):
    # Get demo data
    demo = db_read(db, payload['roomId'])
    name = get_person(session, data['personId'], headers, name='first')[0]

    # Check whether org has been selected
    if 'org_id' in demo:
        post_message(session, headers, payload,
                     f'The organization for this demo has already been set to **[{demo["org_name"]}]({demo["org_url"]})** (ID _{demo["org_id"]}_).')
    else:
        if inputs['existing_org'] == 'yes':
            display_card(session, headers, payload, db, '01_input_key.json')
        else:
            display_card(session, headers, payload, db, '03_org_create.json')


def card_input_key(session, headers, payload, data, inputs, db):
    # Get demo data
    demo = db_read(db, payload['roomId'])
    name = get_person(session, data['personId'], headers, name='first')[0]

    # Check if API key has already been entered
    if 'org_id' in demo:
        last_four = demo['api_key'][-4:]
        post_message(session, headers, payload,
                     f'Hi <@personId:{data["personId"]}|{name}>, your API key ending in _{last_four}_ has already been entered for this demo.')
    else:
        room_id = payload['roomId']
        api_key = inputs['api_key']
        m = meraki.DashboardAPI(api_key, output_log=False)
        try:
            orgs = m.organizations.getOrganizations()
            if len(orgs) == 1:
                org_id = orgs[0]['id']

                # Check that there isn't already a demo associated with the org ID
                demos = get_demos(db)
                demo_orgs = [d for d in demos if 'org_id' in d and 'room_id' in d]
                demo_ids = [d['org_id'] for d in demo_orgs]
                if org_id in demo_ids:
                    demo = demo_orgs[demo_ids.index(org_id)]
                    post_message(session, headers, payload,
                                 f'There already is a demo for the **[{demo["org_name"]}]({demo["org_url"]})** org (ID _{demo["org_id"]}_), so you will be added to that existing space.')
                    # Add user to room
                    payload = {'roomId': room_id, 'personId': data['personId']}
                    session.post('https://api.ciscospark.com/v1/memberships/', headers=headers, json=payload)

                # Go with only choice (single dashboard org)
                else:
                    db_write(db, room_id, {u'api_key': api_key, u'org_id': org_id, u'org_url': orgs[0]['url'], u'org_name': orgs[0]['name']})
                    display_card(session, headers, payload, db, '04_main_menu.json')
            elif len(orgs) > 1:
                choices = []
                max = 100
                if len(orgs) > max:
                    random.shuffle(orgs)
                    orgs = orgs[:max]
                    post_message(session, headers, payload,
                                 f'Hi <@personId:{data["personId"]}|{name}>, that API key has access to many organizations, so only {max} are shown.')
                for org in sorted(orgs, key=lambda o: o['name']):
                    choices.append({'title': org['name'], 'value': f'{org["id"]},{org["url"]},{org["name"]}'})
                db_write(db, room_id, {u'api_key': api_key})
                display_card(session, headers, payload, db, '02_org_select.json', {'list_of_orgs': choices})
        except:
            post_message(session, headers, payload,
                         f'Hi <@personId:{data["personId"]}|{name}>, please check and re-enter your API key.')


def card_org_select(session, headers, payload, data, inputs, db):
    # Get demo data
    room_id = payload['roomId']
    demo = db_read(db, room_id)

    # Check whether org has been selected
    if 'org_id' in demo:
        post_message(session, headers, payload,
                     f'The organization for this demo has already been set to **[{demo["org_name"]}]({demo["org_url"]})** (ID _{demo["org_id"]}_).')
    else:
        org_id, org_url, org_name = inputs['org_choice'].split(',')

        # Check that there isn't already a demo associated with the org ID
        demos = get_demos(db)
        demo_orgs = [d for d in demos if 'org_id' in d and 'room_id' in d]
        demo_ids = [d['org_id'] for d in demo_orgs]
        if org_id in demo_ids:
            demo = demo_orgs[demo_ids.index(org_id)]
            post_message(session, headers, payload,
                         f'There already is a demo for the **[{demo["org_name"]}]({demo["org_url"]})** org (ID _{demo["org_id"]}_), so you will be added to that existing space.')
            # Add user to room
            payload = {'roomId': room_id, 'personId': data['personId']}
            session.post('https://api.ciscospark.com/v1/memberships/', headers=headers, json=payload)

        # Proceed with the org selection
        else:
            db_write(db, payload['roomId'], {u'org_id': org_id, u'org_url': org_url, u'org_name': org_name})
            display_card(session, headers, payload, db, '04_main_menu.json')


def card_org_create(session, headers, payload, data, inputs, db):
    # Get demo data
    room_id = payload['roomId']
    demo = db_read(db, room_id)

    # Check whether org has been selected
    if 'org_id' in demo:
        post_message(session, headers, payload,
                     f'The organization for this demo has already been set to **[{demo["org_name"]}]({demo["org_url"]})** (ID _{demo["org_id"]}_).')
    else:
        cu_name = demo['cu_name']
        api_key = MERAKI_DEMO_API_KEY
        m = meraki.DashboardAPI(api_key, output_log=False)
        org = m.organizations.createOrganization(f'API Demo - {cu_name}')
        db_write(db, room_id, {u'api_key': api_key, u'org_id': org['id'], u'org_url': org['url'], u'org_name': org['name']})
        (name, emails) = get_person(session, data['personId'], headers)
        email = emails[0]
        m.admins.createOrganizationAdmin(org['id'], email, name, 'full')
        post_message(session, headers, payload,
                     f'Hi <@personId:{data["personId"]}|{name}>, a [new org]({org["url"]}) has been created, and you have been added as an admin. Please verify using the link sent to {email}.')

        # Create sites and add devices
        sites = int(inputs['site_count'])
        if sites > 0:
            attempts = 10
            while attempts > 0:
                allocations = get_allocations(db)
                options = [x for x in range(200)]
                slots = [x for x in options if x not in allocations]
                if len(slots) == 0:
                    attempts = 0
                    break
                random.shuffle(slots)
                slot = random.choice(slots)
                db_write(db, room_id, {u'virtual_serials': slot})
                data = db_read(db, room_id)
                if 'virtual_serials' in data and slot == data['virtual_serials']:
                    break
                else:
                    time.sleep(0.5)
            if attempts == 0:
                post_message(session, headers, payload,
                             'No virtual serials are currently available, so networks will be created without devices.')
                serials = None
            else:
                input_file = open('serials.txt').read()
                serials = input_file.split()

            locations = [
                ('San Francisco @ US', '500 Terry A Francois Blvd, San Francisco, CA 94158', 'America/Los_Angeles'),
                ('Chicago @ US', '525 W Van Buren St, Chicago, IL 60607', 'America/Chicago'),
                ('London @ GB', '7 - 8, 10 Finsbury Square, Finsbury, London EC2A 1AF, UK', 'Europe/London'),
                ('Sydney @ AU', 'Level 21/321 Kent St, Sydney NSW 2000, Australia', 'Australia/Sydney'),
                ('Shanghai @ CN', '696 Weihai Road, Jing\'an District Shanghai, Shanghai 200041', 'Asia/Shanghai')
            ]
            for x in range(sites):
                (name, address, tz) = locations.pop(random.randint(1, len(locations)) - 1)
                try:
                    network = m.networks.createOrganizationNetwork(org['id'], f'API demo - {name}',
                                                                   'wireless appliance switch camera',
                                                                   tags='API_demo', timeZone=tz)
                except meraki.APIError as e:
                    post_message(session, headers, payload,
                                 f'There was a problem creating the {name} network: `{e}`')
                else:
                    post_message(session, headers, payload, message=f'Network **{name}** created')
                    if serials:
                        devices = {}
                        devices['Security SD-WAN appliance'] = serials[x * 200 + slot]
                        devices['Switch'] = serials[x * 200 + slot + 1000]
                        devices['Wireless AP'] = serials[x * 200 + slot + 2000]
                        devices['Camera'] = serials[x * 200 + slot + 3000]
                        for k, v in devices.items():
                            try:
                                m.devices.claimNetworkDevices(network['id'], serial=v)
                            except meraki.APIError as e:
                                post_message(session, headers, payload,
                                             f'There was a problem adding serial _{v}_ to {name}: `{e}`')
                            else:
                                try:
                                    m.devices.updateNetworkDevice(network['id'], v, name=k, address=address, moveMapMarker=True,
                                                                  notes='Automated install via your Meraki API demo!')
                                except:
                                    pass
                                else:
                                    post_message(session, headers, payload,
                                                 f'Added device with serial _{v}_')

        time.sleep(6)
        display_card(session, headers, payload, db, '04_main_menu.json')


def card_main_menu(session, headers, payload, data, inputs, db):
    room_id = payload['roomId']
    demo = db_read(db, room_id)
    print(inputs)
    if 'button' in inputs:
        button = inputs['button']
        if button == 'new_site':
            display_card(session, headers, payload, db, '10_new_site.json')
        elif button == 'wifi_psk':
            display_card(session, headers, payload, db, '11_wifi_psk.json')
        elif button == 'isp_health':
            display_card(session, headers, payload, db, '20_loss_latency.json')
        elif button == 'get_devices':
            device_statuses(session, headers, payload, data, inputs, db)
        elif button == 'get_snapshots':
            get_snapshots(session, headers, payload, data, inputs, db)
        elif button == 'get_clients':
            display_card(session, headers, payload, db, '30_get_clients.json')
        elif button == 'send_feedback':
            time_stamp = f'{datetime.now():%Y-%m-%d_%H-%M-%S}'
            coll_ref = db.collection(u'api-feedback')
            doc_ref = coll_ref.document(time_stamp)
            (name, emails) = get_person(session, data['personId'], headers, name='first')
            doc = {
                'name': name,
                'email': emails[0],
                'room_id': room_id,
                'cu_name': demo['cu_name'],
                'feedback': inputs['feedback']
            }
            doc_ref.set(doc)
            post_message(session, headers, payload,
                         f'Thank you so much for your feedback, <@personId:{data["personId"]}|{name}>! Your input has been recorded and will be reviewed by our team.')
        # button == 'manage_demo'
        else:
            if inputs['manageDemoIndex'] == 'add_users':
                display_card(session, headers, payload, db, '80_add_users.json')
            elif inputs['manageDemoIndex'] == 'web_app':
                web_ui(session, headers, payload, db)
            elif inputs['manageDemoIndex'] == 'change_logo':
                display_card(session, headers, payload, db, '83_change_logo.json')
            elif inputs['manageDemoIndex'] == 'configure_webhooks':
                api_key = demo['api_key']
                org_id = demo['org_id']
                m = meraki.DashboardAPI(api_key, output_log=False)
                networks = m.networks.getOrganizationNetworks(org_id)
                tagged_networks = [n for n in networks if n['tags'] and 'API_demo' in n['tags']]
                if tagged_networks:
                    networks = ''
                    for n in tagged_networks:
                        networks += f'{n["name"]}\n'
                    display_card(session, headers, payload, db, '84_webhook_alerts.json',
                                 template={'networks': networks})
                else:
                    post_message(session, headers, payload,
                                 'To configure webhooks, tag at least one network with "API_demo" (case-sensitive) first!')
            elif inputs['manageDemoIndex'] == 'shut_down':
                if demo['api_key'] == MERAKI_DEMO_API_KEY:
                    display_card(session, headers, payload, db, '81_shut_down_org.json')
                else:
                    display_card(session, headers, payload, db, '82_shut_down.json')


def card_new_site(session, headers, payload, data, inputs, db):
    # Get demo and inputs
    demo = db_read(db, payload['roomId'])
    api_key = demo['api_key']
    org_id = demo['org_id']
    org_url = demo['org_url']
    net_name = inputs['txt_name']
    net_name = re.sub(r'[^A-Za-z0-9 .@#_-]+', '', net_name)
    serials = inputs['txt_serials']
    address = inputs['txt_address']
    notes = inputs['txt_notes']

    # Create new network
    m = meraki.DashboardAPI(api_key, output_log=False)
    try:
        network = m.networks.createOrganizationNetwork(org_id, net_name, 'wireless appliance switch camera',
                                                       tags='API_demo', timeZone='US/Eastern')
        net_id = network['id']
    except meraki.APIError as e:
        post_message(session, headers, payload,
                     f'There was a problem trying to create the **{net_name}** network in your [org]({org_url}): `{e}`.')
    else:
        post_message(session, headers, payload,
                     f'New network **{net_name}** created in your [dashboard org]({org_url})')

        # Setup webhook HTTP server and alerts
        server_url = f'https://us-east4-{PROJECT_ID}.cloudfunctions.net/api-demo_dashboard'
        try:
            server = m.http_servers.createNetworkHttpServer(net_id, 'API demo', server_url, sharedSecret='API demo')
            with open('alerts.json') as fp:
                alerts = json.load(fp)
            m.alert_settings.updateNetworkAlertSettings(net_id,
                                                        defaultDestinations={'httpServerIds': [server['id']]},
                                                        alerts=alerts)
        except:
            pass
        else:
            post_message(session, headers, payload,
                         f'**Webhook alerts** successfully enabled for _{net_name}_')

        # Claim serial numbers
        serial_pattern = re.compile(r'[Qq][A-Za-z0-9]{3}-?[A-Za-z0-9]{4}-?[A-Za-z0-9]{4}')
        serials = serial_pattern.findall(serials)
        if serials:
            for serial in serials:
                if serial[4] != '-':
                    serial = serial[:4] + '-' + serial[4:]
                if serial[9] != '-':
                    serial = serial[:9] + '-' + serial[9:]
                serial = serial.upper()
                try:
                    r = m.devices.claimNetworkDevices(net_id, serial=serial)
                except meraki.APIError as e:
                    post_message(session, headers, payload,
                                 f'There was a problem trying to add device **{serial}**: `{e}`')
                else:
                    model = m.devices.getNetworkDevice(net_id, serial)['model']
                    initials = model[:2]
                    if initials == 'MR':
                        device = 'wireless AP'
                    elif initials == 'MX':
                        device = 'security & SD-WAN appliance'
                    elif initials == 'MS':
                        device = 'switch'
                    elif initials == 'MV':
                        device = 'camera'
                    elif initials == 'MG':
                        device = 'cellular gateway'
                    elif initials in ('Z1', 'Z3'):
                        device = 'teleworker gateway'
                    post_message(session, headers, payload,
                                 f'**{model}** {device} (_{serial}_) added')
                    if address or notes:
                        m.devices.updateNetworkDevice(network['id'], serial, address=address, notes=notes,
                                                      moveMapMarker=True, tags='API_demo')

    # Show main menu after a delay
    time.sleep(6)
    display_card(session, headers, payload, db, '04_main_menu.json')


def card_wifi_psk(session, headers, payload, data, inputs, db):
    # Get demo and inputs
    demo = db_read(db, payload['roomId'])
    api_key = demo['api_key']
    org_id = demo['org_id']
    password = inputs['txt_password']
    phones = inputs['txt_phones']

    if len(password) < 8:
        post_message(session, headers, payload,
                     f'You need to enter a password with at least 8 characters!')
    else:
        # Update wireless password
        m = meraki.DashboardAPI(api_key, output_log=False)
        networks = m.networks.getOrganizationNetworks(org_id)
        demo_networks = [n for n in networks if n['tags'] and 'API_demo' in n['tags']]
        updated = False
        for net in demo_networks:
            try:
                m.ssids.updateNetworkSsid(net['id'], '0', name='API demo Wi-Fi', enabled=True,
                                          authMode='psk', encryptionMode='wpa', psk=password)
            except meraki.APIError as e:
                post_message(session, headers, payload,
                             f'There was a problem trying to update the _wireless password_ for network **{net["name"]}**: `{e}`')
            else:
                post_message(session, headers, payload,
                             f'_Wireless password_ updated for network **{net["name"]}**')
                updated = True

        # Send message via text
        if updated:
            auth_id = PLIVO_AUTH_ID
            auth_token = PLIVO_AUTH_TOKEN
            client = plivo.RestClient(auth_id, auth_token)
            message = f'Password to the API demo Wi-Fi network is {password}'

            phone_number = ''.join(filter(str.isdigit, phones))
            reg = re.compile('(\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}|\(\d{3}\)\s*\d{3}[-\.\s]??\d{4}|\d{3}[-\.\s]??\d{4})', re.S)
            reg_results = reg.findall(phone_number)
            for number in reg_results:
                number = f'1{number}' if number[0] != '1' else number
                client.messages.create(src=PLIVO_PHONE_NUMBER, dst=number, text=message)

        # Show main menu after a delay
        time.sleep(6)
        display_card(session, headers, payload, db, '04_main_menu.json')


def wan_health(session, headers, payload, data, inputs, db):
    # Get user inputs on loss & latency
    loss = inputs['txt_loss']
    if loss.isnumeric():
        loss = int(loss)
        loss = loss if loss >= 0 and loss <= 100 else 0
    else:
        loss = 0
    latency = inputs['txt_latency']
    if latency.isnumeric():
        latency = int(latency)
        latency = latency if latency >= 0 else 0
    else:
        latency = 0
    LOSS_THRESHOLD = loss
    LATENCY_THRESHOLD = latency

    # Get demo and inputs
    demo = db_read(db, payload['roomId'])
    api_key = demo['api_key']
    org_id = demo['org_id']
    org_name = demo['org_name']

    # Make dashboard API call
    m = meraki.DashboardAPI(api_key, output_log=False)
    data = m.organizations.getOrganizationUplinksLossAndLatency(org_id)
    num_devices = len(set([d['serial'] for d in data]))

    # Ensure there is data to demo
    if not data or not num_devices:
        post_message(session, headers, payload,
                     f'There is no data on WAN uplinks in your _{org_name}_ org, so using a separate demo environment instead.')
        api_key = SANDBOX_KEY
        org_id = SANDBOX_ORG
        org_name = 'Meraki Launchpad🚀'
        m = meraki.DashboardAPI(api_key, output_log=False)
        data = m.organizations.getOrganizationUplinksLossAndLatency(org_id)
        num_devices = len(set([d['serial'] for d in data]))

    # Process data
    num_uplinks = len(set([(d['serial'], d['uplink']) for d in data]))
    num_probes = len(data)
    loss_data = [d['timeSeries'][-1]['lossPercent'] for d in data]
    loss_count = len([x for x in loss_data if x > LOSS_THRESHOLD])
    latency_data = [d['timeSeries'][-1]['latencyMs'] for d in data]
    latency_count = len([x for x in latency_data if x > LATENCY_THRESHOLD])

    # Display data
    message = f'### Across a total of {num_probes} probes over {num_uplinks} WAN uplinks on {num_devices} appliances:\n  '
    message += f'- {loss_count} of those probes currently have 🕳 packet loss higher than **{LOSS_THRESHOLD:.1f}%**\n  '
    message += f'- {latency_count} of those probes currently have 🐢 latency higher than **{LATENCY_THRESHOLD:.1f} ms**!'
    post_message(session, headers, payload, message)

    # Compile report and attach as file
    flatten = pandas.json_normalize(data, record_path='timeSeries', meta=['networkId', 'serial', 'uplink', 'ip'])
    file_path = f'/tmp/{org_name} - loss latency report.csv'
    flatten.to_csv(file_path)
    send_file(session, headers, payload, 'Attached is the full report for org-wide loss & latency.', file_path, file_type='text/csv')

    # Show main menu after a delay
    time.sleep(6)
    display_card(session, headers, payload, db, '04_main_menu.json')


def device_statuses(session, headers, payload, data, inputs, db):
    # Get demo and inputs
    demo = db_read(db, payload['roomId'])
    api_key = demo['api_key']
    org_id = demo['org_id']
    org_name = demo['org_name']

    # Make dashboard API call and scrub data
    m = meraki.DashboardAPI(api_key, output_log=False)
    data = m.organizations.getOrganizationDeviceStatuses(org_id)
    total = len(data)
    all_virtual = True if False not in ['QBS' == d['serial'][:3] for d in data] else False

    # Ensure there is data to demo
    if total == 0 or all_virtual:
        post_message(session, headers, payload,
                     f'There aren\'t any actual devices in your _{org_name}_ org, so using a separate demo environment instead.')
        m = meraki.DashboardAPI(SANDBOX_KEY, output_log=False)
        data = m.organizations.getOrganizationDeviceStatuses(SANDBOX_ORG)
        org_name = 'Meraki Launchpad🚀'
        total = len(data)
    online_devices = [device for device in data if device['status'] == 'online']
    online = len(online_devices)
    alerting_devices = [device for device in data if device['status'] == 'alerting']
    alerting = len(alerting_devices)
    offline_devices = [device for device in data if device['status'] == 'offline']
    offline = len(offline_devices)

    # Format message, displaying devices names if <= 10 per section
    message = f'### For the **{total}** devices in _{org_name}_:'
    if online > 0:
        plural = 'is' if online == 1 else 'are'
        message += f'  \n- **{online}** {plural} ✅ online ({online / total * 100:.1f}%)'
        if online <= 10:
            message += ': '
            for device in online_devices:
                if device['name']:
                    message += f'{device["name"]}, '
                else:
                    message += f'{device["mac"]}, '
            message = message[:-2]
    if alerting > 0:
        plural = 'is' if alerting == 1 else 'are'
        message += f'  \n- **{alerting}** {plural} ⚠️ alerting_ ({alerting / total * 1004:.1f}%)'
        if alerting <= 10:
            message += ': '
            for device in alerting_devices:
                if device['name']:
                    message += f'{device["name"]}, '
                else:
                    message += f'{device["mac"]}, '
            message = message[:-2]
    if offline > 0:
        plural = 'is' if offline == 1 else 'are'
        message += f'  \n- **{offline}** {plural} ❌ _offline_ ({offline / total * 100:.1f}%)'
        if offline <= 10:
            message += ': '
            for device in offline_devices:
                if device['name']:
                    message += f'{device["name"]}, '
                else:
                    message += f'{device["mac"]}, '
            message = message[:-2]
    post_message(session, headers, payload, message)

    # Show cellular failover information, if applicable
    cellular_online = [device for device in data if
                       'usingCellularFailover' in device and device['status'] == 'online']
    cellular = len(cellular_online)
    if cellular > 0:
        failover_online = [device for device in cellular_online if device['usingCellularFailover'] == True]
        failover = len(failover_online)
        if failover > 0:
            post_message(session, headers, payload,
                         f'> {failover} of {cellular} appliances online ({failover / cellular * 100:.1f}%) using 🗼 cellular failover')

    # Show pie graph
    labels = ['Online', 'Alerting', 'Offline']
    sizes = [online, alerting, offline]
    explode = (0, 0, 0.1)
    colors = ['#00CC00', '#FFEE58', '#CD5C5C']
    fig1, ax1 = plt.subplots()
    ax1.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', shadow=True, startangle=90)
    # Equal aspect ratio ensures that pie is drawn as a circle
    ax1.axis('equal')
    plt.tight_layout()
    file_path = f'/tmp/{org_name} - device statuses.png'
    plt.savefig(file_path)
    send_file(session, headers, payload, 'Graph of org-wide device statuses', file_path,
              file_type='image/png')

    # Compile report and attach as file
    flatten = pandas.json_normalize(data)
    file_path = f'/tmp/{org_name} - device statuses report.csv'
    flatten.to_csv(file_path)
    send_file(session, headers, payload, 'Attached is the full report for org-wide device statuses.', file_path,
              file_type='text/csv')

    # Show main menu after a delay
    time.sleep(6)
    display_card(session, headers, payload, db, '04_main_menu.json')


def get_snapshots(session, headers, payload, data, inputs, db):
    # Get demo and inputs
    demo = db_read(db, payload['roomId'])
    api_key = demo['api_key']
    org_id = demo['org_id']

    # Tell a joke to kill time
    response = session.get('https://icanhazdadjoke.com/', headers={'Accept': 'application/json', 'User-Agent': 'Meraki API demo'})
    if response.ok:
        message = 'Wait a moment while loading your snapshots, so here\'s a joke... 🤣\n'
        message += f'''```\n{response.json()["joke"]}\n'''
        post_message(session, headers, payload, message)

    # Find online cameras from API_demo networks
    m = meraki.DashboardAPI(api_key, output_log=False)
    networks = m.networks.getOrganizationNetworks(org_id)
    network_times = {n['id']: n['timeZone'] for n in networks}
    demo_networks = [n['id'] for n in networks if n['tags'] and 'API_demo' in n['tags']]
    statuses = m.organizations.getOrganizationDeviceStatuses(org_id)
    online_devices = [d['serial'] for d in statuses if d['status']=='online']
    devices = m.devices.getOrganizationDevices(org_id)
    cameras = [d for d in devices if d['model'][:2]=='MV']
    demo_cameras = [c for c in cameras if c['serial'] in online_devices and (c['networkId'] in demo_networks or 'API_demo' in c['tags'])]

    # Ensure demo data, so use another org if needed
    if not demo_cameras:
        post_message(session, headers, payload,
                     f'There are currently no online cameras tagged with _API_demo_ (or in networks with that tag), so using a separate demo environment instead.')
        api_key = SANDBOX_KEY
        org_id = SANDBOX_ORG
        m = meraki.DashboardAPI(api_key, output_log=False)
        networks = m.networks.getOrganizationNetworks(org_id)
        network_times = {n['id']: n['timeZone'] for n in networks}
        statuses = m.organizations.getOrganizationDeviceStatuses(org_id)
        online_devices = [d['serial'] for d in statuses if d['status'] == 'online']
        devices = m.devices.getOrganizationDevices(org_id)
        cameras = [d for d in devices if d['model'][:2] == 'MV']
        demo_cameras = [c for c in cameras if c['serial'] in online_devices]

    # Retrieve snapshots and post into Webex Teams with CV analysis
    random.shuffle(demo_cameras)
    for c in demo_cameras[:3]:
        print(c)
        net_id = c['networkId']
        serial = c['serial']
        cam_name = c['name'] if 'name' in c and c['name'] else serial
        time_zone = network_times[net_id]
        video_link = m.cameras.getNetworkCameraVideoLink(net_id, serial)['url']
        try:
            snapshot_link = m.cameras.generateNetworkCameraSnapshot(net_id, serial)['url']
        except:
            pass
        else:
            utc_now = pytz.utc.localize(datetime.utcnow())
            local_now = utc_now.astimezone(pytz.timezone(time_zone))
            file_name = cam_name + ' - ' + local_now.strftime('%Y-%m-%d_%H-%M-%S')
            temp_file = download_file(session, file_name, snapshot_link)
            if temp_file:
                gcp_vision(session, headers, payload, f'{file_name}.jpg', f'[{cam_name}]({video_link})', '/tmp')
            else:
                post_message(session, headers, payload,
                             f'`GET` error with retrieving snapshot for camera **{cam_name}**')

    # Show main menu after a delay
    time.sleep(6)
    display_card(session, headers, payload, db, '04_main_menu.json')


def get_clients(session, headers, payload, data, inputs, db):
    # Get user input on number of days
    days = inputs['txt_days']
    if days.isnumeric():
        days = int(days)
        days = days if days >= 0 and days <= days else 14
    else:
        days = 14
    DAYS = days

    # Get demo and inputs
    demo = db_read(db, payload['roomId'])
    api_key = demo['api_key']
    org_id = demo['org_id']
    org_name = demo['org_name']

    # Get list of networks in organization
    m = meraki.DashboardAPI(api_key, output_log=False)
    networks = m.networks.getOrganizationNetworks(org_id)
    online = [d for d in m.organizations.getOrganizationDeviceStatuses(org_id) if d['status']=='online']

    # Iterate through networks
    total = len(networks)
    if len(networks) > 100:
        post_message(session, headers, payload,
                     f'Your org is too large, so for demo purposes only the first 100 networks will be analyzed.')
    elif len(networks) == 0 or len(online) == 0:
        post_message(session, headers, payload,
                     f'You do not have online devices in networks, so using data from a separate demo environment instead.')
        m = meraki.DashboardAPI(SANDBOX_KEY, output_log=False)
        networks = m.networks.getOrganizationNetworks(SANDBOX_ORG)
        org_name = 'Meraki Launchpad🚀'

    # Ensure there is at least data on one client
    unfinished = True
    all_clients = []
    while unfinished:
        post_message(session, headers, payload,
                     f'Please wait ⏳ while collecting data on clients...')
        for net in networks[:100]:
            try:
                # Get list of clients on network, filtering on timespan of last X days
                clients = m.clients.getNetworkClients(net['id'], timespan=60*60*24*DAYS, perPage=1000, total_pages='all')
            except meraki.APIError as e:
                post_message(session, headers, payload,
                             f'Skipping network _{net["name"]}_ because of an error: `{e}`')
            else:
                if clients:
                    unfinished = False
                    for c in clients:
                        c['Network Name'] = net['name']
                        c['Network ID'] = net['id']
                        all_clients.append(c)

        if unfinished:
            post_message(session, headers, payload,
                         f'You do not have clients in any networks, so using data from a separate demo environment instead.')
            m = meraki.DashboardAPI(SANDBOX_KEY, output_log=False)
            networks = m.networks.getOrganizationNetworks(SANDBOX_ORG)
            org_name = 'Meraki Launchpad🚀'

    # Stitch together one consolidated CSV per org
    flatten = pandas.json_normalize(all_clients)
    file_path = f'/tmp/{org_name} - clients in last {DAYS} days.csv'
    flatten.to_csv(file_path)

    # Compile report and attach as file
    top_clients = sorted(all_clients, key=lambda c: c['usage']['sent'] + c['usage']['recv'], reverse=True)[:5]
    avg_usage = sum([c['usage']['sent'] + c['usage']['recv'] for c in all_clients]) / len(all_clients) / 1024
    if top_clients:
        plural = 'day' if DAYS == 1 else 'days'
        message = f'### Total of {len(all_clients)} clients in this org within the _last {DAYS} {plural}_; average usage per client of {round(avg_usage):,} MB\n  '
        message += f'Here are the top **{len(top_clients)}** based on bandwidth consumption:'
        for c in top_clients:
            usage = (c['usage']['sent'] + c['usage']['recv']) / 1024
            name = c['description'] if c['description'] and c['description'].lower() != 'none' else c['mac']
            message += f'\n- _{name}_ used {round(usage):,} MB'
        post_message(session, headers, payload, message)
    send_file(session, headers, payload, f'Attached is the report for all clients in the org.', file_path,
              file_type='text/csv')

    # Show main menu after a delay
    time.sleep(6)
    display_card(session, headers, payload, db, '04_main_menu.json')


def card_add_users(session, headers, payload, data, inputs, db):
    # Get demo and inputs
    room_id = payload['roomId']
    demo = db_read(db, room_id)
    api_key = demo['api_key']
    org_id = demo['org_id']
    org_url = demo['org_url']
    org_name = demo['org_name']
    users = demo['users']

    emails = inputs['txt_emails']
    admin = inputs['opt_admin']
    pattern = r'''[\w!#$%&'*+\/=?`{|}~^-]+(?:\.[\w!#$%&'*+\/=?`{|}~^-]+)*@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,6}'''
    emails_pattern = re.compile(pattern)
    addresses = emails_pattern.findall(emails)
    m = meraki.DashboardAPI(api_key, output_log=False)
    users.extend(addresses)
    db_write(db, room_id, {u'users': users})

    for email in addresses:
        add_user(session, email, room_id, headers)
        message = f'Welcome <@personEmail:{email}>! 😀'
        if admin == 'true':
            try:
                m.admins.createOrganizationAdmin(org_id, email, email, 'full')
            except meraki.APIError as e:
                post_message(session, headers, payload,
                             f'There was an error trying to add {email} as a Meraki dashboard admin: `{e}`')
            else:
                message += f' You have been added to the **{org_name}** [org]({org_url}).'
                if '@cisco.com' in email:
                    message += ' (Log in with "personal account" and not "Cisco SSO".)'
        post_message(session, headers, payload, message)


def change_logo(session, headers, payload, data, inputs, db):
    room_id = payload['roomId']
    demo = db_read(db, room_id)
    logo = inputs['txt_logo']

    if logo[-4:] not in ('.jpg', '.png'):
        post_message(session, headers, payload,
                     'Please enter a valid logo URL that ends in ".jpg" or ".png" in order for Webex Teams to display it correctly.')
    else:
        try:
            session.get(logo, timeout=3)
        except:
            post_message(session, headers, payload,
                         f'The website for {logo} does not allow non-browsers to use that image, so your logo remains the same ({demo["logo_url"]}).')
        else:
            db_write(db, room_id, {u'logo_url': logo})
            post_message(session, headers, payload,
                         f'Your demo\'s logo has now been updated to {logo}')
            display_card(session, headers, payload, db, '04_main_menu.json')


def webhook_alerts(session, headers, payload, data, inputs, db):
    if inputs['opt_webhooks'] == 'true':
        # Get demo and inputs
        demo = db_read(db, payload['roomId'])
        api_key = demo['api_key']
        org_id = demo['org_id']
        org_name = demo['org_name']

        # Get list of networks in organization
        m = meraki.DashboardAPI(api_key, output_log=False)
        networks = m.networks.getOrganizationNetworks(org_id)
        tagged_networks = [n for n in networks if n['tags'] and 'API_demo' in n['tags']]

        # Setup webhook HTTP server and alerts for tagged networks
        server_url = f'https://us-east4-{PROJECT_ID}.cloudfunctions.net/api-demo_dashboard'
        for n in tagged_networks:
            try:
                server = m.http_servers.createNetworkHttpServer(n['id'], 'API demo', server_url, sharedSecret='API demo')
                with open('alerts.json') as fp:
                    alerts = json.load(fp)
                m.alert_settings.updateNetworkAlertSettings(n['id'],
                                                            defaultDestinations={'httpServerIds': [server['id']]},
                                                            alerts=alerts)
            except:
                pass
            else:
                post_message(session, headers, payload,
                             f'**Webhook alerts** successfully configured for _{n["name"]}_')

        time.sleep(3)
        display_card(session, headers, payload, db, '04_main_menu.json')


def shut_down(session, headers, payload, data, inputs, db):
    if inputs['opt_shut'] == 'No':
        post_message(session, headers, payload,
                     'Your demo continues to run!')
    else:
        post_message(session, headers, payload, 'Shutting down, please wait...')
        room_id = payload['roomId']
        demo = db_read(db, room_id)
        if 'web_url' in demo:
            service = demo['web_url'][8:].split(RUN_DOMAIN)[0]
            gsession = gcloud_session()
            del_service(gsession, service)

        m = meraki.DashboardAPI(demo['api_key'], output_log=False)
        org_id = demo['org_id']
        if 'virtual_serials' in demo:
            slot = demo['virtual_serials']
            input_file = open('serials.txt').read()
            serials = input_file.split()
            allocation = []
            for x in range(5):
                allocation.append(serials[x * 200 + slot])
                allocation.append(serials[x * 200 + slot + 1000])
                allocation.append(serials[x * 200 + slot + 2000])
                allocation.append(serials[x * 200 + slot + 3000])

            org_serials = m.devices.getOrganizationDevices(org_id)
            org_serial_list = [d['serial'] for d in org_serials]
            for serial in allocation:
                if serial in org_serial_list:
                    index = org_serial_list.index(serial)
                    m.devices.removeNetworkDevice(org_serials[index]['networkId'], serial)

        users = demo['users']
        (user_name, user_emails) = get_person(session, data['personId'], headers)
        message = f'Thank you so much 🥂 for demoing **Meraki APIs** 💚! ' \
                  f'Your _{demo["cu_name"]}_ environment has been shut down by {user_name} ({user_emails[0]}).'
        if 'virtual_serials' in demo:
            message += '\n\nThe virtual serials allocated to you have been unclaimed from your networks.'

        if 'opt_org' in inputs and inputs['opt_org'] == 'true':
            networks = m.networks.getOrganizationNetworks(org_id)
            for n in networks:
                m.networks.deleteNetwork(n['id'])
            admins = m.admins.getOrganizationAdmins(org_id)
            for a in admins:
                if a['email'] != 'meraki.api.lab@gmail.com':
                    m.admins.deleteOrganizationAdmin(org_id, a['id'])
            new_name = demo['org_name'].replace('API Demo - ', 'Completed Demo - ')
            m.organizations.updateOrganization(org_id, name=new_name)
            message = message[:-1] + ', and your dashboard org has been removed.'
            db_write(db, room_id, {u'org_name': new_name})

        for user in users:
            post_message(session, headers, {'toPersonEmail': user}, message)
        del_room(session, room_id, headers)
        del_demo(db, room_id)
