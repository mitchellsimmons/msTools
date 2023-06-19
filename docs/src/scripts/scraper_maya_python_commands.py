import datetime
import json
import os
import requests
from bs4 import BeautifulSoup
import urllib2


# ----------------------------------------------------------------------------
# --- Utilities ---
# ----------------------------------------------------------------------------

def _getYearQualifiedUrl(url):
    year = int(datetime.date.today().year)
    recursionLimit = 0
    while requests.get(url.format(year=year)).status_code != 200 and recursionLimit < 5:
        year -= 1
        recursionLimit += 1

    return url.format(year=year)


# ----------------------------------------------------------------------------
# --- Const ---
# ----------------------------------------------------------------------------

# This is the root url to the Maya Python API 2.0
root_url = _getYearQualifiedUrl("http://help.autodesk.com/cloudhelp/{year}/ENU/Maya-Tech-Docs/CommandsPython")
index_url = root_url + "/index_all.html"
command_url = root_url + "/{href}"


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

def getGlobalUrlMapping():
    """Return a dictionary containing the urls to every function in the Maya commands documentation

    .. warning::
        This function will run extremely slow

    The structure of the mapping will be as follows:
        mapping = {
            "project": "url",
            "functions": {
                "parent": "url",
                "duplicate": "url",
                ...
            }
        }
    """
    global_url_mapping = {"project": root_url}
    global_url_mapping["commands"] = {}

    parser = 'html.parser'
    resp = urllib2.urlopen(index_url)
    soup = BeautifulSoup(resp, parser, from_encoding=resp.info().getparam('charset'))

    for link in soup.find_all('a', href=True):
        href = link['href']
        commandName = link.contents[0]
        global_url_mapping["commands"][commandName] = command_url.format(href=href)

    return global_url_mapping


def writeGlobalUrlMapping(fileName="urls_maya_python_commands.json"):
    """Dump the url mapping to a json file

    If we want to use this data with a UI, it is impractical to be making http requests
    We need a static cache from which we can load data

    .. warning::
        This function will run extremely slow (the output is over 1mb)
    """
    global_url_mapping = getGlobalUrlMapping()
    outputPath = os.path.join(os.path.dirname(__file__), fileName)
    with open(outputPath, 'w') as outputFile:
        json.dump(global_url_mapping, outputFile)


if __name__ == "__main__":
    writeGlobalUrlMapping("..\\data\\urls_maya_python_commands.json")
