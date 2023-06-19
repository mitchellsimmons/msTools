#!python3
"""
Script builds a url mapping with the following structure:

.. code-block:: python

    {
        "project": "url",
        "modules": {
            "QtWidgets": "url"
        },
        "classes": {
            "QtWidgets": {
                "QWidget": "url"
            }
        },
        "members": {
            "QtWidgets": {
                "QWidget": {
                    "close": "url"
                }
            }
        }
    }
"""
import json
import os
import re
import sphobjinv as soi  # DEPENDENCY: https://pypi.org/project/sphobjinv/


# ----------------------------------------------------------------------------
# --- Constants ---
# ----------------------------------------------------------------------------

ROOT_URL = "https://doc.qt.io/qtforpython-5/"


MISSING_URLS = {
    "PySide2.QtCore.Signal": {
        "role": "class",
        "uri": "PySide2/QtCore/Signal.html"
    },
    "PySide2.QtCore.Slot": {
        "role": "class",
        "uri": "PySide2/QtCore/Slot.html"
    }
}

INVENTORY_URL = "https://doc.qt.io/qtforpython-5/objects.inv"


# ----------------------------------------------------------------------------
# --- Main ---
# ----------------------------------------------------------------------------

def getUrlMapping():
    inv = soi.Inventory(url=INVENTORY_URL)

    for name, data in MISSING_URLS.items():
        inv.objects.append(soi.DataObjStr(name=name, domain='py', role=data['role'], priority='1', uri=data['uri'], dispname='-'))

    urlMapping = {"project": ROOT_URL}
    urlMapping["modules"] = {}
    urlMapping["classes"] = {}
    urlMapping["members"] = {}

    for obj in inv.objects:
        name = obj.name
        nameTokens = name.split(".")
        numNameTokens = len(nameTokens)

        if nameTokens[0] == "PySide2":
            # Uncompress uris (since we need to change the names)
            obj.uri = obj.uri.replace("$", obj.name)

            # Simplify names
            if numNameTokens > 3 and len(re.findall("PySide2", name)) == 2:
                if nameTokens[0] == nameTokens[2] and nameTokens[1] == nameTokens[3]:
                    # Eg. `PySide2.QtWidgets.PySide2.QtWidgets.QWidget.close` -> `PySide2.QtWidgets.QWidget.close`
                    obj.name = ".".join(nameTokens[2:])

            # Record data
            name = obj.name
            nameTokens = name.split(".")
            url = ROOT_URL + obj.uri
            role = obj.role

            if role == "module":
                assert len(nameTokens) == 2, name
                # Remove anchor if it exists
                url = url.split("#")[0]
                urlMapping["modules"][nameTokens[1]] = url

            elif role == "class":
                assert len(nameTokens) == 3, name
                # Remove the anchor
                url = url.split("#")[0]

                if nameTokens[1] in urlMapping["classes"]:
                    urlMapping["classes"][nameTokens[1]][nameTokens[2]] = url
                else:
                    urlMapping["classes"][nameTokens[1]] = {nameTokens[2]: url}

            elif role == "attribute" or role == "method":
                assert len(nameTokens) == 4, name

                if nameTokens[1] in urlMapping["members"]:
                    if nameTokens[2] in urlMapping["members"][nameTokens[1]]:
                        urlMapping["members"][nameTokens[1]][nameTokens[2]][nameTokens[3]] = url
                    else:
                        urlMapping["members"][nameTokens[1]][nameTokens[2]] = {nameTokens[3]: url}
                else:
                    urlMapping["members"][nameTokens[1]] = {nameTokens[2]: {nameTokens[3]: url}}

    # Fill in null data
    for moduleName in urlMapping["modules"]:
        if urlMapping["classes"].get(moduleName) is None:
            urlMapping["classes"][moduleName] = {}
            urlMapping["members"][moduleName] = {}

    for moduleName in urlMapping["modules"]:
        for className in urlMapping["classes"][moduleName]:
            if urlMapping["members"][moduleName].get(className) is None:
                urlMapping["members"][moduleName][className] = {}

    return urlMapping


def writeUrlMapping(outputPath):
    urlMapping = getUrlMapping()

    with open(outputPath, 'w') as outputFile:
        json.dump(urlMapping, outputFile)


if __name__ == "__main__":
    outputPath = os.path.abspath(os.path.join(__file__, "..\\..\\resources\\data\\PySide2Doc_urls.json"))
    writeUrlMapping(outputPath)
