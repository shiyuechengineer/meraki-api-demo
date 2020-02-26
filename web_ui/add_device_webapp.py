# docker build -t ui . && docker run --rm -p 80:80 -e PORT=80 ui

# gcloud builds submit --tag gcr.io/meraki-dev-sd2s/web_ui
# gcloud run deploy web-ui --region=us-east4 --image=gcr.io/meraki-dev-sd2s/web_ui --platform=managed --memory=2048M

# https://create-bot-gkcg2fo2ma-ue.a.run.app/create?customer_name=USPS


#INSTALL AND RUN INSTRUCTIONS
#
#Change the 'apikey' and 'organizationid' variables to match your Meraki Organization
#
#python3 -m venv venv
#. venv/bin/activate
#pip install flask flask-wtf wtforms requests
#
#export FLASK_APP=add_device_webapp.py
#flask run --host=0.0.0.0
#

import os
import merakiapi
from flask import Flask, render_template, redirect, flash, Markup
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, TextAreaField, PasswordField, BooleanField, validators
import datetime
import re, sys
import requests

#CHANGE THESE TO MATCH DESIRED MERAKI ORGANIZATION
apikey = os.environ.get('API_KEY')
organizationid = os.environ.get('ORG_ID')
logo_url = os.environ.get('LOGO_URL')

r = requests.get(logo_url, stream=True)
if r.ok:
    path = f'static/logo'
    with open(path, 'wb') as f:
        for chunk in r:
            f.write(chunk)


#NETWORK DROPDOWN
networks = merakiapi.getnetworklist(apikey, organizationid)
cleannetworks = []
for network in networks:
    for key, value in network.items():
        if key == 'id':
            net_id = value
        elif key == 'name':
            net_name = value
        else:
            continue
    cleannetworks.append([net_id,net_name])
cleannetworks.sort(key=lambda x:x[1])
cleannetworks.insert(0, [None, '* Choose...'])

#TEMPLATE DROPDOWN
templates = merakiapi.gettemplates(apikey, organizationid)
cleantemplates = []
for template in templates:
    for key, value in template.items():
        if key == 'id':
            template_id = value
        elif key == 'name':
            template_name = value
        else:
            continue
    cleantemplates.append([template_id,template_name])
cleantemplates.sort(key=lambda x:x[1])
cleantemplates.insert(0, ["", '* No Template'])

#TAG DROPDOWN
networks = merakiapi.getnetworklist(apikey, organizationid)
tags = []
tagchoices = []
hubchoices = []
networktypes = ['combined', 'appliance']
for network in networks:
    if ('combined' in network['type']) or ('appliance' in network['type']):
        hubchoices.append([network['id'],network['name']])
    if network['tags'] == '':
        continue
    else:
        temptags = str(network['tags']).split(' ')
        for tag in temptags:
            if (tag.strip() not in tags) and ('None' not in tag.strip()):
                tags.append(tag.strip())
                tagchoices.append([tag.strip(), tag.strip()])

hubchoices.sort(key=lambda x:x[1])
hubchoices.insert(0, ['none', '* Choose...'])

tagchoices.sort(key=lambda x:x[1])

#BUILD FORM FIELDS AND POPULATE DROPDOWN 
class AddProvisionForm(FlaskForm):
    #ADDRESS FIELD
    addressField = TextAreaField('Street Address:&nbsp;&nbsp;', [validators.Optional(), validators.length(max=200)])
    
    #SERIAL NUMBER FIELDS
    serialField1 = StringField('Serial Number 1*:&nbsp;', [validators.InputRequired(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField2 = StringField('Serial Number 2:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField3 = StringField('Serial Number 3:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField4 = StringField('Serial Number 4:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField5 = StringField('Serial Number 5:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField6 = StringField('Serial Number 6:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField7 = StringField('Serial Number 7:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField8 = StringField('Serial Number 8:&nbsp;&nbsp;')
        
    nameField1 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField2 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField3 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField4 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField5 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField6 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField7 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField8 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    
    networkField = SelectField(u'Network Name', choices = cleannetworks)
    
    submitField = SubmitField('Submit')

class CreateProvisionForm(FlaskForm):
    #ADDRESS FIELD
    addressField = TextAreaField('Street Address:&nbsp;&nbsp;', [validators.Optional(), validators.length(max=200)])

    #NETWORK CREATE FIELD
    networkTextField = StringField('New Network Name*', [validators.InputRequired()])
    
    templateField = SelectField(u'Template to bind to*', choices = cleantemplates)

    #SERIAL NUMBER FIELDS
    serialField1 = StringField('Serial Number 1*:&nbsp;', [validators.InputRequired(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField2 = StringField('Serial Number 2:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField3 = StringField('Serial Number 3:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField4 = StringField('Serial Number 4:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField5 = StringField('Serial Number 5:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField6 = StringField('Serial Number 6:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField7 = StringField('Serial Number 7:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    serialField8 = StringField('Serial Number 8:&nbsp;&nbsp;')
    
    nameField1 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField2 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField3 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField4 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField5 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField6 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField7 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    nameField8 = StringField('Device Name:&nbsp;&nbsp;', [validators.Optional()])
    
    submitField = SubmitField('Submit')

class ReplaceDevice(FlaskForm):
    networkField = SelectField(u'Network Name', choices = cleannetworks)
	
	#SERIAL NUMBER FIELDS
    oldMX = StringField('MX to Replace:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    newMX = StringField('New MX:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
	
    oldSwitch = StringField('Switch to Replace:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    newSwitch = StringField('New Switch:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
	
    oldAP = StringField('AP to Replace:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
    newAP = StringField('New AP:&nbsp;&nbsp;', [validators.Optional(), validators.Length(min=14, max=14, message='Invalid format. Must be Q2XX-XXXX-XXXX')])
	
    submitField = SubmitField('Submit')
    
class SSIDForm(FlaskForm):

    networkField = SelectField(u'Network Name', choices = cleannetworks)

    #ADDRESS FIELD
    ssidname = StringField('SSID Name:&nbsp;', [validators.Optional()])
    ssidenabled = SelectField('Enabled:&nbsp;', choices=[('enabled', 'Enabled'), ('disabled', 'Disabled')])
    ssidpsk = PasswordField('Pre-Shared Key:&nbsp;', [validators.Optional()])
    ssidvlanid = StringField('VLAN ID:&nbsp;', [validators.Optional()])
    ssidipassignment = SelectField('IP Assignment Mode:&nbsp;', choices=[('Bridge mode', 'Bridge Mode'), ('NAT mode', 'NAT Mode'), ('Layer 3 roaming', 'Layer 3 Roaming')])
    
    submitField = SubmitField('Submit')
        
class BulkForm(FlaskForm):

    tagField = SelectField(u'Network Tag to Apply Changes to: ', choices = tagchoices)

    #IPS
    setips = BooleanField('IPS:&nbsp')
    ipsmode = SelectField('Mode:&nbsp;', choices=[('disabled', 'Disabled'), ('detection', 'Detection'), ('prevention', 'Prevention')])
    ipsrules = SelectField('Rule Set:&nbsp;', choices=[('connectivity', 'Connectivity'), ('balanced', 'Balanced'), ('security', 'Security')])

    #URL Filtering
    set_content_filtering_url = BooleanField('Content Filtering URL Rule:&nbsp')
    content_filtering_url_section = SelectField('Section:&nbsp;',
                          choices=[('blockedUrlPatterns', 'Blocked URL patterns'), ('allowedUrlPatterns', 'Whitelisted URL patterns')])

    content_filtering_url_action = SelectField('Action:&nbsp;',
                                                choices=[('add', 'Add'),
                                                         ('delete', 'Remove')])

    content_filtering_url_list = TextAreaField('Rule Set :&nbsp;', )

    # Content Filtering
    set_content_filtering_categirues = BooleanField('Content Filtering Categories:&nbsp')

    content_filtering_url_action = SelectField('Action:&nbsp;',
                                               choices=[('add', 'Add'),
                                                        ('delete', 'Remove')])

    content_filtering_url_list = TextAreaField('Rule Set :&nbsp;')

    #VPN
    setvpn = BooleanField('VPN Hub Config:&nbsp')
    hub1 = SelectField('1:&nbsp;', choices=hubchoices)
    default1 = BooleanField('Default Route?:&nbsp')
    hub2 = SelectField('2:&nbsp;', choices=hubchoices)
    default2 = BooleanField('Default Route?:&nbsp')
    hub3 = SelectField('3:&nbsp;', choices=hubchoices)
    default3 = BooleanField('Default Route?:&nbsp')
    
    #PSK
    setpsk = BooleanField('SSID PSK:&nbsp')
    ssidnum = SelectField('SSID Number:&nbsp;', choices=[('0','1'), ('1','2'), ('2','3'), ('3','4'), ('4','5')])
    ssidpsk = PasswordField('PSK:&nbsp;', [validators.Optional()])
    
    submitField = SubmitField('Submit')


#MAIN PROGRAM
app = Flask(__name__)
app.config['SECRET_KEY'] = 'Ikarem123'

@app.route('/', methods=['GET', 'POST'])
def provision():
    form = AddProvisionForm()
    if form.validate_on_submit():
        message = []
        postSerials = []
        postNames = []
        
        postNetwork = form.networkField.data
        
        #BUILD ARRAY OF SERIAL NUMBERS FROM FORM
        postSerials.append(form.serialField1.data)
        postSerials.append(form.serialField2.data)
        postSerials.append(form.serialField3.data)
        postSerials.append(form.serialField4.data)
        postSerials.append(form.serialField5.data)
        postSerials.append(form.serialField6.data)
        postSerials.append(form.serialField7.data)
        postSerials.append(form.serialField8.data)
        postSerials = [element.upper() for element in postSerials]; postSerials
        
        postNames.append(form.nameField1.data)
        postNames.append(form.nameField2.data)
        postNames.append(form.nameField3.data)
        postNames.append(form.nameField4.data)
        postNames.append(form.nameField5.data)
        postNames.append(form.nameField6.data)
        postNames.append(form.nameField7.data)
        postNames.append(form.nameField8.data)
        #print(postSerials)
        
        for i,serial in enumerate(postSerials):
            #SKIP EMPTY SERIAL NUMBER TEXT BOXES
            if serial is '':
                continue
            #EASTER EGG
            elif "ILOVEMERAKI" in serial:
                message = Markup("<img src='/static/meraki.png' />")
            else:
                result = merakiapi.adddevtonet(apikey, postNetwork, serial)
                if result == None:
                    #SET ADDRESS AND NAME
                    merakiapi.updatedevice(apikey, postNetwork, serial, name=postNames[i], address=form.addressField.data, move='true')
                    #API RETURNS EMPTY ON SUCCESS, POPULATE SUCCESS MESSAGE MANUALLY
                    netname = merakiapi.getnetworkdetail(apikey, postNetwork)
                    message = Markup('Device with serial <strong>{}</strong> successfully added to Network: <strong>{}</strong>'.format(serial, netname['name']))
                #404 MESSAGE FOR INVALID SERIAL IS BLANK, POPULATE ERROR MESSAGE MANUALLY
                elif result == 'noserial':
                    message = 'Invalid serial {}'.format(serial)
                else:
                    message = result
            #SEND MESSAGE TO SUBMIT PAGE
            flash(message)
        return redirect('/submit')
    return render_template('index.html', title='Meraki Device Provisioning', form=form)
    
@app.route('/createnetwork', methods=['GET', 'POST'])
def provisionNetwork():
    form = CreateProvisionForm()
    if form.validate_on_submit():
        message = []
        postSerials = []
        postNames = []
        
        postNetwork = form.networkTextField.data
        #print(postNetwork)
        
        postTemplate = form.templateField.data
        
        #BUILD ARRAY OF SERIAL NUMBERS FROM FORM
        postSerials.append(form.serialField1.data)
        postSerials.append(form.serialField2.data)
        postSerials.append(form.serialField3.data)
        postSerials.append(form.serialField4.data)
        postSerials.append(form.serialField5.data)
        postSerials.append(form.serialField6.data)
        postSerials.append(form.serialField7.data)
        postSerials.append(form.serialField8.data)
        postSerials = [element.upper() for element in postSerials]; postSerials
        
        postNames.append(form.nameField1.data)
        postNames.append(form.nameField2.data)
        postNames.append(form.nameField3.data)
        postNames.append(form.nameField4.data)
        postNames.append(form.nameField5.data)
        postNames.append(form.nameField6.data)
        postNames.append(form.nameField7.data)
        postNames.append(form.nameField8.data)

        #CREATE NETWORK AND BIND TO TEMPLATE
        result = merakiapi.addnetwork(apikey, organizationid, postNetwork, "appliance switch wireless", "", "America/Los_Angeles")
        
        #GET NEW NETWORK ID
        networks = merakiapi.getnetworklist(apikey, organizationid)
        for network in networks:
            if network['name'] == postNetwork:
                newnetwork = network['id']
                break
        message = Markup("New Network created: <strong>{}</strong> with ID: <strong>{}</strong>".format(postNetwork, newnetwork))
        flash(message)
        
        #BIND TO TEMPLATE
        if form.templateField.data is not "":
            bindresult = merakiapi.bindtotemplate(apikey, newnetwork, postTemplate)
            message = Markup("Network: <strong>{}</strong> bound to Template: <strong>{}</strong>".format(postNetwork, postTemplate))
            flash(message)

        #ADD SERIALS TO NETWORK
        for i,serial in enumerate(postSerials):
            #SKIP EMPTY SERIAL NUMBER TEXT BOXES
            if serial is '':
                continue
            #EASTER EGG
            elif "ILOVEMERAKI" in serial:
                message = Markup("<img src='/static/meraki.png' />")
            else:
                result = merakiapi.adddevtonet(apikey, newnetwork, serial)
                if result == None:
                    #SET ADDRESS AND NAME
                    merakiapi.updatedevice(apikey, newnetwork, serial, name=postNames[i], address=form.addressField.data, move='true')
                    #API RETURNS EMPTY ON SUCCESS, POPULATE SUCCESS MESSAGE MANUALLY
                    netname = merakiapi.getnetworkdetail(apikey, newnetwork)
                    message = Markup('Device with serial <strong>{}</strong> successfully added to Network: <strong>{}</strong>'.format(serial, netname['name']))
                #404 MESSAGE FOR INVALID SERIAL IS BLANK, POPULATE ERROR MESSAGE MANUALLY
                elif result == 'noserial':
                    message = Markup('Invalid serial <strong>{}</strong>'.format(serial))
                else:
                    message = result
            #SEND MESSAGE TO SUBMIT PAGE
            flash(message)
        return redirect('/submit')
    return render_template('indextemplate.html', title='Meraki Device Provisioning', form=form)

@app.route('/replace', methods=['GET', 'POST'])
def replaceForm():
    form = ReplaceDevice()
    if form.validate_on_submit():
        message = []
        
        postNetwork = form.networkField.data
        netname = merakiapi.getnetworkdetail(apikey, postNetwork)
        oldMX = form.oldMX.data
        newMX = form.newMX.data
        oldSwitch = form.oldSwitch.data
        newSwitch = form.newSwitch.data
        oldAP = form.oldAP.data
        newAP = form.newAP.data
        
        if oldMX is not '':
            oldconfig = merakiapi.getdevicedetail(apikey, postNetwork, oldMX)
            merakiapi.updatedevice(apikey, postNetwork, newMX, name=oldconfig['name'], tags=oldconfig['tags'], lat=oldconfig['lat'],
                 lng=oldconfig['lng'], address=oldconfig['address'], move='true')
            result = merakiapi.removedevfromnet(apikey, postNetwork, oldMX)
            if result == None:
                message = Markup('MX with serial <strong>{}</strong> successfully deleted from Network: <strong>{}</strong>'.format(oldMX, netname['name']))
            merakiapi.claim(apikey, organizationid, serial=newMX)
            result = merakiapi.adddevtonet(apikey, postNetwork, newMX)
            if result == None:
                message = Markup('MX with serial <strong>{}</strong> successfully added to Network: <strong>{}</strong>'.format(newMX, netname['name']))
        
        if oldSwitch is not '':
            #ADD NEW SWITCH TO NETWORK
            merakiapi.claim(apikey, organizationid, serial=newSwitch)
            result = merakiapi.adddevtonet(apikey, postNetwork, newSwitch)
            oldconfig = merakiapi.getdevicedetail(apikey, postNetwork, oldSwitch)
            merakiapi.updatedevice(apikey, postNetwork, newSwitch, name=oldconfig['name'], tags=oldconfig['tags'], lat=oldconfig['lat'],
                 lng=oldconfig['lng'], address=oldconfig['address'], move='true')
            if result == None:
                message = Markup('Switch with serial <strong>{}</strong> successfully added to Network: <strong>{}</strong>'.format(newSwitch, netname['name']))
                #CLONE L2 PORT CONFIGS
                if '24' in oldconfig['model']:
                    numports = 30
                elif '48' in oldconfig['model']:
                    numports = 54
                elif '16' in oldconfig['model']:
                    numports = 22
                elif '32' in oldconfig['model']:
                    numports = 38
                for port in range(1, numports):
                    config = merakiapi.getswitchportdetail(apikey, oldSwitch, port)
                    print(config)
                    # Clone corresponding new switch
                    # Tags needed to be input as a list
                    #if config['tags'] is not '':
                    #    tags = config['tags'].split()
                    #else:
                    tags = []

					# Access type port
                    if config['type'] == 'access':
                        merakiapi.updateswitchport(apikey, newSwitch, port,
                            name=config['name'], tags=tags, enabled=config['enabled'],
                            porttype=config['type'], vlan=config['vlan'], voicevlan=config['voiceVlan'],
                            poe='true', isolation=config['isolationEnabled'], rstp=config['rstpEnabled'],
                            stpguard=config['stpGuard'], accesspolicynum=config['accessPolicyNumber'])
					# Trunk type port
                    elif config['type'] == 'trunk':
                        merakiapi.updateswitchport(apikey, newSwitch, port,
                            name=config['name'], tags=tags, enabled=config['enabled'],
                            porttype=config['type'], vlan=config['vlan'], allowedvlans=config['allowedVlans'],
                            poe='true', isolation=config['isolationEnabled'], rstp=config['rstpEnabled'],
                            stpguard=config['stpGuard'])
            #404 MESSAGE FOR INVALID SERIAL IS BLANK, POPULATE ERROR MESSAGE MANUALLY
            elif result == 'noserial':
                message = Markup('Invalid serial <strong>{}</strong>'.format(newSwitch))
            else:
                message = result
            #REMOVE OLD SWITCH FROM NETWORK
            merakiapi.removedevfromnet(apikey, postNetwork, oldSwitch)
        
        if oldAP is not '':
            oldconfig = merakiapi.getdevicedetail(apikey, postNetwork, oldAP)
            merakiapi.updatedevice(apikey, postNetwork, newAP, name=oldconfig['name'], tags=oldconfig['tags'], lat=oldconfig['lat'],
                 lng=oldconfig['lng'], address=oldconfig['address'], move='true')
            result = merakiapi.removedevfromnet(apikey, postNetwork, oldAP)
            if result == None:
                message = Markup('AP with serial <strong>{}</strong> successfully deleted from Network: <strong>{}</strong>'.format(oldMX, netname['name']))
            merakiapi.claim(apikey, organizationid, serial=newAP)
            result = merakiapi.adddevtonet(apikey, postNetwork, newAP)
            if result == None:
                message = Markup('AP with serial <strong>{}</strong> successfully added to Network: <strong>{}</strong>'.format(newMX, netname['name']))

        #SEND MESSAGE TO SUBMIT PAGE
        flash(message)
        return redirect('/submit')
    return render_template('replace.html', title='Meraki Device Provisioning', form=form)
    
@app.route('/ssid', methods=['GET', 'POST'])
def ssidupdate():
    form = SSIDForm()
    if form.validate_on_submit():
        message = []
        
        ssidnum = '0'
        name = form.ssidname.data
        if form.ssidenabled.data == 'enabled':
            enabled = 'true'
        else:
            enabled = 'false'
        authmode = 'psk'
        encryptionmode = 'wpa'
        if len(form.ssidpsk.data) == 0:
            psk = None
        else:
            psk = form.ssidpsk.data
        ipassignmentmode = form.ssidipassignment.data
        vlan = form.ssidvlanid.data
        
        postNetwork = form.networkField.data
        print(postNetwork)
        
        result = merakiapi.updatessid(apikey, postNetwork, ssidnum, name, enabled, authmode, encryptionmode, ipassignmentmode, psk, vlan, suppressprint=False)
        
        if result == None:
            netname = merakiapi.getnetworkdetail(apikey, postNetwork)
            message = Markup('SSID Successfully updated for Network: <strong>{}</strong>'.format(netname['name']))
        else:
            message = result             

        #SEND MESSAGE TO SUBMIT PAGE
        flash(message)
        return redirect('/submit')
    return render_template('ssid.html', title='Meraki SSID Provisioning', form=form)
    
@app.route('/bulk', methods=['GET', 'POST'])
def bulkupdate():
    form = BulkForm()
    if form.validate_on_submit():
        message = []
        
        allnetworkstochange = []
        mxnetworkstochange = []
        mrnetworkstochange = []
        networks = merakiapi.getnetworklist(apikey, organizationid)
        
        for network in networks:
            mxnetworktypes = ['combined', 'appliance']
            mrnetworktypes = ['combined', 'wireless']
            if (network['tags'] == ''):
                continue
            else:
                temptags = str(network['tags']).split(' ')
                for tag in temptags:
                    if tag.strip() == form.tagField.data:
                        allnetworkstochange.append(network['id'])
                        if any(x in network['type'] for x in mxnetworktypes):
                            mxnetworkstochange.append(network['id'])
                        if any(x in network['type'] for x in mrnetworktypes):
                            mrnetworkstochange.append(network['id'])
                        continue
        
        #SET IPS
        if form.setips.data == True:
            for network in mxnetworkstochange:
                netname = merakiapi.getnetworkdetail(apikey, network)
                print("CHANGING IPS SETTINGS FOR NETWORK: {}".format(netname['name']))
                if form.ipsmode.data == 'disabled':
                    result = merakiapi.updateintrusion(apikey, network, mode=form.ipsmode.data)
                else:
                    result = merakiapi.updateintrusion(apikey, network, mode=form.ipsmode.data, idsRulesets=form.ipsrules.data)
                if result == None:
                    message.append('IPS settings successfully updated for Network: <strong>{}</strong>'.format(netname['name']))
                else:
                    message.append(result)

        # SET URL Filtering
        if form.set_content_filtering_url.data:
            for mx_network in mxnetworkstochange:
                mx_network_name = merakiapi.getnetworkdetail(apikey, mx_network)
                print("CHANGING URL FILTERING SETTINGS FOR NETWORK: {}".format(mx_network_name['name']))
                result = merakiapi.edit_content_filtering_url(apikey, mx_network_name['id'], form.content_filtering_url_action.data, form.content_filtering_url_section.data, form.content_filtering_url_list.data.splitlines())

                if not result:
                    message.append('URL filtering rules successfully updated for Network: <strong>{}</strong>'.format(
                        netname['name']))
                else:
                    message.append(result)
        
        ###FINISH VPN            
        if form.setvpn.data == True:
            hubnets = []
            defaults = []
            if 'none' not in form.hub1.data:
                hubnets.append(form.hub1.data)
                defaults.insert(0, form.default1.data)
                if 'none' not in form.hub2.data:
                    hubnets.append(form.hub2.data)
                    defaults.insert(1, form.default2.data)
                    if 'none' not in form.hub3.data:
                        hubnets.append(form.hub3.data)
                        defaults.insert(2, form.default3.data)
            for network in mxnetworkstochange:
                vpnsettings = merakiapi.getvpnsettings(apikey, network)
                print(vpnsettings)
                if 'subnets' in vpnsettings:
                    merakiapi.updatevpnsettings(apikey, network, mode='spoke', subnets=vpnsettings['subnets'], hubnetworks=hubnets, defaultroute=defaults)
                else:
                    merakiapi.updatevpnsettings(apikey, network, mode='spoke', hubnetworks=hubnets, defaultroute=defaults)
                
        #SET SSID PSK
        if form.setpsk.data == True:
            for network in mrnetworkstochange:
                ssid = merakiapi.getssiddetail(apikey, network, form.ssidnum.data)
                result = merakiapi.updatessid(apikey, network, form.ssidnum.data, ssid['name'], ssid['enabled'], ssid['authMode'], ssid['encryptionMode'], ssid['ipAssignmentMode'], form.ssidpsk.data)
        
                if result == None:
                    message = Markup('SSID Successfully updated for Network: <strong>{}</strong>'.format(network))
                else:
                    message = result             


        #SEND MESSAGE TO SUBMIT PAGE
        flash(message)
        return redirect('/submit')
    return render_template('bulk.html', title='Meraki Bulk Changes', form=form)

@app.route('/submit')
def submit():
   return render_template('submit.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
