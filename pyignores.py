import os.path
import sys
import maya
import argparse
import ruamel.yaml
import snyk
import json

from pathlib import Path

# Example usage:
# python /path/to/pyignore.py --orgId d8ff2b65-aec4-426e-a0dd-a9dc626b6f95 --prjId d8b7bdcc-ffd2-49b9-abf2-7d1927d9b730 --apiKey f2e63d96-2741-58ab-b6f8-e43d0b30882c
# Note that the API key is optional, by default it'll be otherwise taken from the ~/.config/configstore/snyk.json file

def get_default_token_path():
    home = str(Path.home())
    default_token_path = "%s/.config/configstore/snyk.json" % home
    return default_token_path

def get_token(token_file_path):
    path = token_file_path
    try:
        with open(path, "r") as f:
            json_obj = json.load(f)
            token = json_obj["api"]
            return token
    except FileNotFoundError as fnfe:
        print("Snyk auth token not found at %s" % path)
        print("Run `snyk auth` (see https://github.com/snyk/snyk#installation) or manually create this file with your token.")
        raise fnfe
    except KeyError as ke:
        print("Snyk auth token file is not properly formed: %s" % path)
        print("Run `snyk auth` (see https://github.com/snyk/snyk#installation) or manually create this file with your token.")
        raise ke


def parse_command_line_args():
    parser = argparse.ArgumentParser(description="Snyk API Examples")
    parser.add_argument(
        "--orgId", type=str, help="The Snyk Organisation Id", required=True,
    )
    parser.add_argument(
        "--prjId", type = str, help = "The Snyk Project Id", required = True
    )
    parser.add_argument(
        "--apiKey", type = str, help = "The Snyk API Key", required = False
    )
    return parser.parse_args()

def get_latest_reason_and_expire(next_issue_ignores):
    latest = None
    yaml_from_api = ""
    for next_ignore in next_issue_ignores:
        for i_key in next_ignore.keys():
            i_value = next_ignore[i_key]
            reason = i_value["reason"]
            expires_date = i_value["expires"]
            dt = maya.parse(expires_date).datetime()
            if ((latest==None or dt>latest) and dt>maya.now().datetime()):
                latest = dt
                yaml_from_api = ""
                yaml_from_api += "        reason: %s \n" % reason
                yaml_from_api += "        expires: %s \n" % expires_date
    return yaml_from_api

def compare_expires(i1, i2):
    i1_expires = None
    i2_expires = None
    for i_key in i1[0].keys():
        i_value = i1[0][i_key]
        i1_expires = i_value["expires"]
    for i_key in i2[0].keys():
        i_value = i2[0][i_key]
        i2_expires = i_value["expires"]
    return maya.parse(i1_expires).datetime() > maya.parse(i2_expires).datetime()

args = parse_command_line_args()

snyk_token = args.apiKey
if (snyk_token == None):
    snyk_token_path = get_default_token_path()
    snyk_token = get_token(snyk_token_path)

org_id = args.orgId
prj_id = args.prjId
show_dependencies = True
show_projects = True
client = snyk.SnykClient(snyk_token)
projects = client.organizations.get(org_id).projects.all()
proj = client.organizations.get(org_id).projects.get(prj_id)

project_id = proj.id
project_name = proj.name
ignores = proj.ignores.all()

yaml_from_api = ""

if len(ignores) > 0:
    yaml_from_api += "ignore:\n"
    for next_issue_id in ignores.keys():
        next_issue_ignores = ignores[next_issue_id]
        latest_reason_and_expire = get_latest_reason_and_expire(next_issue_ignores)
        if (latest_reason_and_expire != ""):
            yaml_from_api += "  %s:\n" % next_issue_id
            yaml_from_api += "    - '*':\n"
            yaml_from_api += latest_reason_and_expire
    yaml_from_api += "patch: {}"

yaml = ruamel.yaml.YAML()
# if a .snyk file exists in folder, load it as basis, otherwise use dummy template instead
if (os.path.isfile('.snyk')):
    with open('.snyk') as fp:
        data = yaml.load(fp)
else:
    data = yaml.load("""\
# Snyk (https://snyk.io) policy file, patches or ignores known vulnerabilities.
version: v1.19.0
# ignores vulnerabilities until expiry date; change duration by modifying expiry date
ignore:
  dummy:
  - '*':
      reason: Just a dummy
      expires: 1970-01-01T19:26:08.142000Z  
    """)

# merge ignores loaded from API with .snyk ignores
data1 = yaml.load(yaml_from_api)
for i in data1['ignore']:
    if i in data['ignore'] and i in data1['ignore']:
        print("ignore in both... " + i)
        if (compare_expires(data1['ignore'][i], data['ignore'][i])):
            data['ignore'].update({i:data1['ignore'][i]})
    else:
        data['ignore'].update({i: data1['ignore'][i]})

yaml.dump(data, sys.stdout)

# create a new file with merged yaml
yaml.dump(data, open('/tmp/.snyk', 'w'))

# then run: snyk test --policy-path=/tmp/.snyk
