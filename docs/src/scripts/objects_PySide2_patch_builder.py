#!python3
import os
import re
import sphobjinv as soi

# The following script builds a modified object inventory for PySide2.
# The default PySide2 objects.inv file found at 'https://doc.qt.io/qtforpython-5/objects.inv' uses an inconvenient referencing format
# whereby a method such as `QtWidgets.QWidget.close` needs to be referenced as :meth:`PySide2.QtWidgets.PySide2.QtWidgets.QWidget.close`.
# This script produces an inventory that contains a more convenient referencing format,
# whereby the same method can be referenced as :meth:`PySide2.QtWidgets.QWidget.close`.

pythonInvPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..\\data\\objects_PySide_v2.inv'))
invOutputPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..\\data\\objects_PySide_v2_patch.inv'))

inv = soi.Inventory(pythonInvPath)
inv.project = "PySide"
inv.version = '2.0'

missing = {
    "PySide2.QtCore.Signal": {
        "role": "class",
        "uri": "PySide2/QtCore/Signal.html"
    },
    "PySide2.QtCore.Slot": {
        "role": "class",
        "uri": "PySide2/QtCore/Slot.html"
    }
}

for obj in inv.objects:
    uri = obj.uri
    name = obj.name
    nameTokens = name.split(".")
    numNameTokens = len(nameTokens)

    if numNameTokens > 3 and len(re.findall("PySide2", name)) == 2:
        if nameTokens[0] == nameTokens[2] and nameTokens[1] == nameTokens[3]:
            if numNameTokens > 4:
                if nameTokens[3] == nameTokens[4]:
                    # Handle names like `PySide2.Qt3DAnimation.PySide2.Qt3DAnimation.Qt3DAnimation.QAbstractAnimation.duration`
                    if numNameTokens > 5:
                        newName = ".".join([nameTokens[0], nameTokens[1]] + nameTokens[5:])
                    else:
                        newName = ".".join([nameTokens[0], nameTokens[1]])
                else:
                    # Handle names like `PySide2.QtWidgets.PySide2.QtWidgets.QWidget.close`
                    newName = ".".join([nameTokens[0], nameTokens[1]] + nameTokens[4:])
            else:
                newName = ".".join([nameTokens[0], nameTokens[1]])

        obj.name = newName
        obj.uri = obj.uri.replace("$", name)

for name, data in missing.items():
    inv.objects.append(soi.DataObjStr(name=name, domain='py', role=data['role'], priority='1', uri=data['uri'], dispname='-'))

# Generate data
textData = inv.data_file(contract=True)

# Compress data
ztext = soi.compress(textData)

# Save to disk
soi.writebytes(invOutputPath, ztext)
