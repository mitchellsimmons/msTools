#!python3
import json
import os
import sphobjinv as soi

# NOTE : The sphinx PythonDomain class maps basic object type names (eg. 'module', 'function', 'method') to role names (eg. 'mod', 'func', 'meth')
# - sphobjinv uses the object types names to register objects in the inventory
# - However when we want to cross-reference these objects in our documentation we must use the corresponding role name
# - See the PythonDomain class for the object_types mapping:
#   https://github.com/sphinx-doc/sphinx/blob/2fac698e764ac28dec86844624f4ac415ea11a37/sphinx/domains/python.py#L1100

# If we have rebuilt the commands data (json file) make sure the year is updated below
mayaCommandsUrlPrefix = "http://help.autodesk.com/cloudhelp/2020/ENU/Maya-Tech-Docs/CommandsPython/"
lenMayaCommandsUrlPrefix = len(mayaCommandsUrlPrefix)
mayaCommandsDataPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..\\data\\urls_maya_python_commands.json'))
invOutputPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..\\data\\objects_maya_python_commands.inv'))
jsonOutputPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..\\data\\objects_maya_python_commands.json'))

inv = soi.Inventory()
inv.project = "Maya Python Commands"
inv.version = '1.0'

with open(mayaCommandsDataPath, 'r') as outputFile:
    urlMapping = json.load(outputFile)

    for commandName, commandUrl in urlMapping["commands"].items():
        objName = ".".join(["cmds", commandName])
        relativeUri = commandUrl[lenMayaCommandsUrlPrefix:]
        # Even though commands are technically classes, they are used like functions
        obj = soi.DataObjStr(name=objName, domain='py', role='function', priority='1', uri=relativeUri, dispname='-')
        inv.objects.append(obj)

# Generate data
textData = inv.data_file(contract=True)
jsonData = inv.json_dict(contract=True)

# Compress data
ztext = soi.compress(textData)

# Save to disk
soi.writebytes(invOutputPath, ztext)

with open(jsonOutputPath, "w") as jsonOutputFile:
    json.dump(jsonData, jsonOutputFile)
