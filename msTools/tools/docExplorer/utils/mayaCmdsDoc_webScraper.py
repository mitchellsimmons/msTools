"""
Script builds a url mapping with the following structure:

.. code-block:: python

    {
        "project": "url",
        "commands": {
            "parent": "url",
            "duplicate": "url",
        }
    }
"""
import datetime
import json
import os
import requests    # DEPENDENCY: https://pypi.org/project/requests/
from bs4 import BeautifulSoup  # DEPENDENCY: https://pypi.org/project/beautifulsoup4/
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
# --- Constants ---
# ----------------------------------------------------------------------------

# This is the root url to the Maya Python API 2.0
ROOT_URL = _getYearQualifiedUrl("http://help.autodesk.com/cloudhelp/{year}/ENU/Maya-Tech-Docs/CommandsPython")
INDEX_URL = ROOT_URL + "/index_all.html"
COMMAND_URL = ROOT_URL + "/{href}"


# ----------------------------------------------------------------------------
# --- Main ---
# ----------------------------------------------------------------------------

def getUrlMapping():
    urlMapping = {"project": ROOT_URL}
    urlMapping["commands"] = {}

    parser = 'html.parser'
    resp = urllib2.urlopen(INDEX_URL)
    soup = BeautifulSoup(resp, parser, from_encoding=resp.info().getparam('charset'))

    for link in soup.find_all('a', href=True):
        href = link['href']
        commandName = link.contents[0]
        urlMapping["commands"][commandName] = COMMAND_URL.format(href=href)

    return urlMapping


def writeUrlMapping(outputPath):
    urlMapping = getUrlMapping()

    with open(outputPath, 'w') as outputFile:
        json.dump(urlMapping, outputFile)


if __name__ == "__main__":
    outputPath = os.path.abspath(os.path.join(__file__, "..\\..\\resources\\data\\mayaCmdsDoc_urls.json"))
    writeUrlMapping(outputPath)
