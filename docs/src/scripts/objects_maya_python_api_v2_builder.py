#!python3
import json
import os
import sphobjinv as soi

# NOTE : The sphinx PythonDomain class maps basic object type names (eg. 'module', 'function', 'method') to role names (eg. 'mod', 'func', 'meth')
# - sphobjinv uses the object types names to register objects in the inventory
# - However when we want to cross-reference these objects in our documentation we must use the corresponding role name
# - See the PythonDomain class for the object_types mapping:
#   https://github.com/sphinx-doc/sphinx/blob/2fac698e764ac28dec86844624f4ac415ea11a37/sphinx/domains/python.py#L1100

om2UrlPrefix = "https://help.autodesk.com/view/MAYAUL/2020/ENU/"
lenOm2UrlPrefix = len(om2UrlPrefix)
om2DataPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..\\data\\urls_maya_python_api_v2.json'))
invOutputPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..\\data\\objects_maya_python_api_v2.inv'))
jsonOutputPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..\\data\\objects_maya_python_api_v2.json'))

inv = soi.Inventory()
inv.project = "Maya Python API"
inv.version = '2.0'

with open(om2DataPath, 'r') as outputFile:
    urlMapping = json.load(outputFile)

    for moduleName, moduleUrl in urlMapping["modules"].items():
        objName = moduleName
        relativeUri = moduleUrl[lenOm2UrlPrefix:]
        obj = soi.DataObjStr(name=objName, domain='py', role='module', priority='1', uri=relativeUri, dispname='-')
        inv.objects.append(obj)

        for className, classUrl in urlMapping["classes"][moduleName].items():
            objName = ".".join([moduleName, className])
            relativeUri = classUrl[lenOm2UrlPrefix:]
            obj = soi.DataObjStr(name=objName, domain='py', role='class', priority='1', uri=relativeUri, dispname='-')
            inv.objects.append(obj)

            for memberName, memberUrl in urlMapping["members"][moduleName][className].items():
                objName = ".".join([moduleName, className, memberName])
                relativeUri = memberUrl[lenOm2UrlPrefix:]
                # Because I am unable to determine whether members are methods or attributes, I will add both roles to the inventory
                # This will give the user the ability to decide what role to use with a member (ie. `meth` will display with brackets)
                # eg. :meth:`OpenMaya.MAngle.asUnits` or :attr:`OpenMaya.MAngle.kDegrees`
                obj = soi.DataObjStr(name=objName, domain='py', role='method', priority='1', uri=relativeUri, dispname='-')
                inv.objects.append(obj)
                obj = soi.DataObjStr(name=objName, domain='py', role='attribute', priority='2', uri=relativeUri, dispname='-')
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
