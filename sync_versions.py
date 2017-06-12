#!/usr/bin/python

import osimport json
import base64
import urllib2
import xml.etree.ElementTree as ET from distutils.version 
import LooseVersion

###############################################################
#                         CONFIG SECTION                      #
Jira = {}
Jira['username'] = "cdets"
Jira['password'] = "syncme"
Jira['projects'] = [ 'SON4', 'SON5' ]
CDETS = {}
CDETS['username'] = "akaptsan"
CDETS['apiurl'] = '2.4' #prod
CDETS['token'] = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX" #prod
#CDETS['apiurl'] = '2.4-dev' #stage
#CDETS['token'] = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXX" #stage
CDETS['project'] = "CSC.spapps"
CDETS['product'] = "qson"
###############################################################

################ GET VERSIONS FROM JIRA ###################
versions = []
for projectname in Jira['projects']:
    request = urllib2.Request('https://ic-jira.cisco.com/rest/api/2/project/' + projectname + '/versions') 
    base64string = base64.encodestring('%s:%s' % (Jira['username'], Jira['password'])).replace('\n', '') 
    request.add_header("Authorization", "Basic %s" % base64string)  
    
    responce = urllib2.urlopen(request)  
    
    json_reply = json.loads(responce.read())  
    
    for versionObject in json_reply:  
        versions.append(versionObject["name"]) 
#Remove string versions from list
versions = [ v for v in versions if v[0].isdigit() ]

versions.sort()
JiraVersions = versions

print "Jira Versions:"
print JiraVersions

#################### GET VERSIONS FROM CDETS ###################
versions = []

request = urllib2.Request('http://cdetsng.cisco.com/wsapi/' + CDETS['apiurl'] + '/api/values/Version/Project=' + CDETS['project'] + ',Product=' + CDETS['product'] + '/refresh')
base64string = base64.encodestring('%s:%s' % (CDETS['username'], CDETS['token'])).replace('\n', '')
request.add_header("Authorization", "Basic %s" % base64string)

responce = urllib2.urlopen(request) xml_reply = ET.fromstring(responce.read()) 

for xml_version in xml_reply[0][0]: 
    versions.append(xml_version.get('value'))

#Remove string versions from list
versions = [ v for v in versions if v[0].isdigit() ]

versions.sort()
CDETSVersions = versions

print "CDETS Versions:"
print CDETSVersions

################### COMPARING VERSIONS ###################
markedFound = []

for JiraVersion in JiraVersions: 
    for CDETSVersion in CDETSVersions:  
        if (LooseVersion(JiraVersion) == LooseVersion(CDETSVersion)):   
            markedFound.append(JiraVersion) 

print "Jira Versions found in CDETS:"
print markedFound

toadd = list(set(JiraVersions) - set(markedFound))
toadd.sort()

# If nothing to add
if not toadd: 
    print "No new versions should be added to CDETS" 
    exit(0)
else: 
    print "Jira Versions that should be added into CDETS:" 
    print toadd

################ ADDING VERSION TO CDETS ##################
xml_toadd = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + \            
            '<FieldValue xmlns="cdetsng" name="Project" value="' + CDETS['project'] +'" xmlns:ns1="http://www.w3.org/1999/xlink">\n' + \            
            '<FieldValue name="Product" value="' + CDETS['product'] + '">\n'

for Version in toadd: 
    xml_toadd += '<FieldValue name="Version" value="' + Version + '"/>\n'

xml_toadd += '</FieldValue>\n' + \             
             '</FieldValue>\n'

print xml_toadd

request = urllib2.Request('http://cdetsng.cisco.com/wsapi/' + CDETS['apiurl'] + '/api/values/Version', data=xml_toadd)
base64string = base64.encodestring('%s:%s' % (CDETS['username'], CDETS['token'])).replace('\n', '')
request.add_header("Authorization", "Basic %s" %base64string)
request.add_header('Content-Type', 'application/xml')
request.get_method = lambda: 'PUT'

responce = urllib2.urlopen(request)

print responce.read()

################ GENERATING CONFIG ####################
f = open("son_config_prod.xml", "r")
contents = f.readlines()
f.close() 

mapping = []
for Version in toadd: 
    mapping.append('               <value_mapping jira="' + Version + '" cdets="' + Version + '"/>')

mapping = "\n".join(mapping) + "\n"

### Here goes magic. We need to add versions to specific 
### places in the config. Firstly, we found lines with
### "Backlog" and write down line numbers.
### Here by "lines" really means id of line in list.
### But, after adding mappins before first "Backlog" line,
### Next "Backlog" goes down on one line, so, to initial 
### list of "Backlog" line numbers we need to add:
### to first element - nothing
### to second element - one line
### to third element - two lines

placestoinsert = []

for id, line in enumerate(contents): 
    if (line.find("Backlog") > 0):  
        placestoinsert.append(id)

elements_toadd = len(toadd)

for id, line in enumerate(placestoinsert): 
    placestoinsert[id] = line + id 

for line in placestoinsert: 
    contents.insert(line, mapping)

f = open("son_config_prod.xml", "w")
contents = "".join(contents)
f.write(contents)
f.close()

# Pushing modified config to git
os.system("git remote rm origin")
os.system("git remote add origin " + os.environ['bamboo_repository_git_repositoryUrl'])
os.system("git add son_config_prod.xml")
os.system("git commit -m 'Adding versions " + ", ".join(toadd) + "'")
os.system("git push")
