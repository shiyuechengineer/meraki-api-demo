from datetime import datetime

import pytz
import requests

from chatbot import *
from status import *


# List the devices in an organization
# https://api.meraki.com/api_docs#list-the-devices-in-an-organization
def get_org_devices(session, api_key, org_id):
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}
    response = session.get(f'https://api.meraki.com/api/v0/organizations/{org_id}/devices', headers=headers)
    return response.json()


# Returns video link to the specified camera. If a timestamp is supplied, it links to that timestamp.
# https://api.meraki.com/api_docs#returns-video-link-to-the-specified-camera
def get_video_link(api_key, net_id, serial, timestamp=None, session=None):
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    if not session:
        session = requests.Session()

    if timestamp:
        response = session.get(
            f'https://api.meraki.com/api/v0/networks/{net_id}/cameras/{serial}/videoLink?timestamp={timestamp}',
            headers=headers
        )
    else:
        response = session.get(
            f'https://api.meraki.com/api/v0/networks/{net_id}/cameras/{serial}/videoLink',
            headers=headers
        )

    if response.ok:
        video_link = response.json()['url']
        return video_link
    else:
        return None


# Generate a snapshot of what the camera sees at the specified time and return a link to that image.
# https://api.meraki.com/api_docs#generate-a-snapshot-of-what-the-camera-sees-at-the-specified-time-and-return-a-link-to-that-image
def generate_snapshot(api_key, net_id, serial, timestamp=None, session=None):
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    if not session:
        session = requests.Session()

    if timestamp:
        response = session.post(
            f'https://api.meraki.com/api/v0/networks/{net_id}/cameras/{serial}/snapshot',
            headers=headers,
            json={'timestamp': timestamp}
        )
    else:
        response = session.post(
            f'https://api.meraki.com/api/v0/networks/{net_id}/cameras/{serial}/snapshot',
            headers=headers
        )

    if response.ok:
        snapshot_link = response.json()['url']
        return snapshot_link
    else:
        return None


# List the devices in a network
# https://api.meraki.com/api_docs#list-the-devices-in-a-network
def get_network_devices(api_key, net_id, session=None):
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    if not session:
        session = requests.Session()

    response = session.get(
        f'https://api.meraki.com/api/v0/networks/{net_id}/devices',
        headers=headers
    )

    if response.ok:
        return response.json()
    else:
        return None


# Return a network
# https://api.meraki.com/api_docs#return-a-network
def get_network(api_key, net_id, session=None):
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    if not session:
        session = requests.Session()

    response = session.get(
        f'https://api.meraki.com/api/v0/networks/{net_id}',
        headers=headers
    )

    if response.ok:
        return response.json()
    else:
        return None


# Retrieve cameras' snapshots, links to video, and timestamps in local time zone
def meraki_snapshots(session, api_key, timestamp=None, cameras=None):
    # Temporarily store mappings of networks to their time zones
    network_times = {}

    # Assemble return data
    snapshots = []
    for camera in cameras:
        net_id = camera['networkId']
        serial = camera['serial']
        cam_name = camera['name'] if 'name' in camera and camera['name'] else serial

        # Get time zone
        if net_id not in network_times:
            time_zone = get_network(api_key, net_id, session)['timeZone']
            network_times[net_id] = time_zone
        else:
            time_zone = network_times[net_id]

        # Get video link
        video_link = get_video_link(api_key, net_id, serial, timestamp, session)

        # Get snapshot link
        snapshot_link = generate_snapshot(api_key, net_id, serial, timestamp, session)

        # Add timestamp to file name
        if not timestamp:
            utc_now = pytz.utc.localize(datetime.utcnow())
            local_now = utc_now.astimezone(pytz.timezone(time_zone))
            file_name = cam_name + ' - ' + local_now.strftime('%Y-%m-%d_%H-%M-%S')
        else:
            file_name = cam_name

        # Add to list of snapshots to send
        snapshots.append((cam_name, file_name, snapshot_link, video_link))

    return snapshots


# Determine whether to retrieve all cameras or just selected snapshots
def return_snapshots(session, headers, payload, api_key, org_id, message, labels):
    try:
        # Get org's devices
        devices = get_org_devices(session, api_key, org_id)
        cameras = [d for d in devices if d['model'][:2] == 'MV']
        statuses = get_device_statuses(session, api_key, org_id)
        online = [d['serial'] for d in statuses if d['status'] == 'online']

        # All cameras in the org that are online
        if message_contains(message, ['all', 'complete', 'entire', 'every', 'full']) or not labels:
            post_message(session, headers, payload,
                        '📸 _Retrieving all cameras\' snapshots..._')
            online_cams = []
            for c in cameras:
                if c['serial'] in online:
                    online_cams.append(c)
            snapshots = meraki_snapshots(session, api_key, None, online_cams)

        # Or just specified/filtered ones, skipping those that do not match filtered names/tags
        else:
            post_message(session, headers, payload,
                        '📷 _Retrieving camera snapshots..._')
            filtered_cams = []
            for c in cameras:
                if 'name' in c and c['name'] in labels:
                    filtered_cams.append(c)
                elif 'tags' in c and set(labels).intersection(c['tags'].split()):
                    filtered_cams.append(c)
            snapshots = meraki_snapshots(session, api_key, None, filtered_cams)

        # Send cameras names with files (URLs)
        for (cam_name, file_name, snapshot, video) in snapshots:
            if snapshot:
                temp_file = download_file(session, file_name, snapshot)
                if temp_file:
                    # Send snapshot without analysis
                    # send_file(session, headers, payload, f'[{cam_name}]({video})', temp_file, file_type='image/jpg')

                    # Send to computer vision API for analysis
                    import cv_gcp
                    cv_gcp.gcp_vision(session, headers, payload, temp_file, f'[{cam_name}]({video})')
                # Snapshot GET with URL did not return any image
                else:
                    post_message(session, headers, payload,
                                f'GET error with retrieving snapshot for camera **{cam_name}**')
            else:
                # Snapshot POST was not successful in retrieving image URL
                post_message(session, headers, payload,
                            f'POST error with requesting snapshot for camera **{cam_name}**')
    except:
        post_message(session, headers, payload,
                     'Does your API key have write access to the specified organization ID with cameras? 😳')
