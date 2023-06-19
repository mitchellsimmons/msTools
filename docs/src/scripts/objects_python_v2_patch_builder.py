#!python3
import os
import sphobjinv as soi

# The following script builds an object inventory to allow for more consistent cross-referencing in our documentation
# The default Python objects.inv file does not include logical roles for certain objects
# For example we have to use :func:`tuple` or :obj:`tuple` since tuple is documented as a function not a type
# Certain objects such as list do not even have a role which we can cross-reference

pythonInvPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..\\data\\objects_python_v2.inv'))
invOutputPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..\\data\\objects_python_v2_patch.inv'))

inv = soi.Inventory(pythonInvPath)
inv.project = "Python"
inv.version = '2.7'

# Append `class` objects
inv.objects.append(soi.DataObjStr(name="tuple", domain='py', role='class', priority='1', uri="library/functions.html#tuple", dispname='-'))
inv.objects.append(soi.DataObjStr(name="list", domain='py', role='class', priority='1', uri="library/functions.html#func-list", dispname='-'))
inv.objects.append(soi.DataObjStr(name="basestring", domain='py', role='class', priority='1', uri="library/functions.html#basestring", dispname='-'))

# Generate data
textData = inv.data_file(contract=True)

# Compress data
ztext = soi.compress(textData)

# Save to disk
soi.writebytes(invOutputPath, ztext)
