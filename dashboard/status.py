from statistics import mean

from chatbot import *

LOSS_THRESHOLD = 7.0
LATENCY_THRESHOLD = 49.0

base_url = 'https://api.meraki.com/api/v0'


# List the organizations that the user has privileges on
# https://api.meraki.com/api_docs#list-the-organizations-that-the-user-has-privileges-on
def get_organizations(session, api_key):
    headers = {'X-Cisco-Meraki-API-Key': api_key}
    response = session.get(f'{base_url}/organizations', headers=headers)
    return response.json() if response.ok else None


# List the status of every Meraki device in the organization
# https://api.meraki.com/api_docs#list-the-status-of-every-meraki-device-in-the-organization
def get_device_statuses(session, api_key, org_id):
    headers = {'X-Cisco-Meraki-API-Key': api_key}
    response = session.get(f'{base_url}/organizations/{org_id}/deviceStatuses', headers=headers)
    return response.json() if response.ok else None


# Return the uplink loss and latency for every MX in the organization from at latest 2 minutes ago
# https://api.meraki.com/api_docs#return-the-uplink-loss-and-latency-for-every-mx-in-the-organization-from-at-latest-2-minutes-ago
def get_orgs_uplinks(session, api_key, org_id):
    headers = {'X-Cisco-Meraki-API-Key': api_key}
    response = session.get(f'{base_url}/organizations/{org_id}/uplinksLossAndLatency', headers=headers)
    return response.json() if response.ok else None


# Return the inventory for an organization
# https://api.meraki.com/api_docs#return-the-inventory-for-an-organization
def get_org_inventory(session, api_key, org_id):
    headers = {'X-Cisco-Meraki-API-Key': api_key}
    response = session.get(f'{base_url}/organizations/{org_id}/inventory', headers=headers)
    return response.json() if response.ok else None


# List the networks in an organization
# https://api.meraki.com/api_docs#list-the-networks-in-an-organization
def get_networks(session, api_key, org_id, configTemplateId=None):
    get_url = f'{base_url}/organizations/{org_id}/networks'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}
    if configTemplateId:
        get_url += f'?configTemplateId={configTemplateId}'
    response = session.get(get_url, headers=headers)
    return response.json() if response.ok else None


# List the networks in an organization
# https://api.meraki.com/api_docs#list-the-networks-in-an-organization
def get_networks(session, api_key, org_id, configTemplateId=None):
    get_url = f'{base_url}/organizations/{org_id}/networks'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}
    if configTemplateId:
        get_url += f'?configTemplateId={configTemplateId}'
    response = session.get(get_url, headers=headers)
    return response.json() if response.ok else None


# Create a network
# https://api.meraki.com/api_docs#create-a-network
def create_network(session, api_key, org_id, name=None, type=None, tags=None, timeZone=None,
                   copyFromNetworkId=None, disableMyMerakiCom=None, disableRemoteStatusPage=None):
    post_url = f'{base_url}/organizations/{org_id}/networks'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    variables = ['name', 'type', 'tags', 'timeZone', 'copyFromNetworkId', 'disableMyMerakiCom', 'disableRemoteStatusPage']
    payload = {key: value for (key, value) in locals().items()
               if key in variables and value is not None}

    response = session.post(post_url, headers=headers, json=payload)
    return response.json() if response.ok else None


# Claim a device into a network
# https://api.meraki.com/api_docs#claim-a-device-into-a-network
def claim_device(session, api_key, net_id, serial):
    post_url = f'{base_url}/networks/{net_id}/devices/claim'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    payload = {'serial': serial}

    response = session.post(post_url, headers=headers, json=payload)
    return True if response.ok else False


# Update the attributes of a device
# https://api.meraki.com/api_docs#update-the-attributes-of-a-device
def update_device(session, api_key, net_id, serial, name=None, tags=None, lat=None, lng=None, address=None, notes=None,
                  moveMapMarker=None, switchProfileId=None, floorPlanId=None):
    put_url = f'{base_url}/networks/{net_id}/devices/{serial}'
    headers = {'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'}

    variables = ['name', 'tags', 'lat', 'lng', 'address', 'notes', 'moveMapMarker', 'switchProfileId', 'floorPlanId']
    payload = {key: value for (key, value) in locals().items()
               if key in variables and value is not None}

    response = session.put(put_url, headers=headers, json=payload)
    print(payload)
    return response.json() if response.ok else response.status_code, response.text


# Return device status for each org
def device_status(session, headers, payload, api_key):
    orgs = get_organizations(session, api_key)
    responded = False

    for org in orgs:

        # Skip Meraki corporate for admin users
        if org['id'] == 1:
            continue

        # Org-wide device statuses
        statuses = get_device_statuses(session, api_key, org['id'])
        if statuses:

            # Tally devices across org
            total = len(statuses)
            online_devices = [device for device in statuses if device['status'] == 'online']
            online = len(online_devices)
            alerting_devices = [device for device in statuses if device['status'] == 'alerting']
            alerting = len(alerting_devices)
            offline_devices = [device for device in statuses if device['status'] == 'offline']
            offline = len(offline_devices)

            # Format message, displaying devices names if <= 10 per section
            message = f'### **{org["name"]}**'
            if online > 0:
                message += f'  \n- {online} devices ✅ online ({online / total * 100:.1f}%)'
                if online <= 10:
                    message += ': '
                    for device in online_devices:
                        if device['name']:
                            message += f'{device["name"]}, '
                        else:
                            message += f'{device["mac"]}, '
                    message = message[:-2]

            if alerting > 0:
                message += f'  \n- _{alerting} ⚠️ alerting_ ({alerting / total * 1004:.1f}%)'
                if alerting <= 10:
                    message += ': '
                    for device in alerting_devices:
                        if device['name']:
                            message += f'{device["name"]}, '
                        else:
                            message += f'{device["mac"]}, '
                    message = message[:-2]

            if offline > 0:
                message += f'  \n- **{offline} ❌ offline** ({offline / total * 100:.1f}%)'
                if offline <= 10:
                    message += ': '
                    for device in offline_devices:
                        if device['name']:
                            message += f'{device["name"]}, '
                        else:
                            message += f'{device["mac"]}, '
                    message = message[:-2]

            post_message(session, headers, payload, message)
            responded = True

            # Show cellular failover information, if applicable
            cellular_online = [device for device in statuses if
                               'usingCellularFailover' in device and device['status'] == 'online']
            cellular = len(cellular_online)
            if cellular > 0:
                failover_online = [device for device in cellular_online if device['usingCellularFailover'] == True]
                failover = len(failover_online)

                if failover > 0:
                    post_message(session, headers, payload,
                                 f'> {failover} of {cellular} appliances online ({failover / cellular * 100:.1f}%) using 🗼 cellular failover')

        # Org-wide uplink performance
        uplinks = get_orgs_uplinks(session, api_key, org['id'])
        if uplinks:

            # Tally up uplinks with worse performance than thresholds here
            loss_count = 0
            latency_count = 0

            for uplink in uplinks:
                perf = uplink['timeSeries']

                loss = mean([sample['lossPercent'] for sample in perf])
                if loss > LOSS_THRESHOLD and loss < 100.0:  # ignore probes to unreachable IPs that are incorrectly configured
                    loss_count += 1

                latency = mean([sample['latencyMs'] for sample in perf])
                if latency > LATENCY_THRESHOLD:
                    latency_count += 1

            if loss_count > 0:
                post_message(session, headers, payload,
                             f'{loss_count} device-uplink-probes currently have 🕳 packet loss higher than **{LOSS_THRESHOLD:.1f}%**!')
            if latency_count > 0:
                post_message(session, headers, payload,
                             f'{latency_count} device-uplink-probes currently have 🐢 latency higher than **{LATENCY_THRESHOLD:.1f} ms**!')

    if not responded:
        post_message(session, headers, payload,
                     'Does your API key have access to at least a single org with API enabled? 😫')
