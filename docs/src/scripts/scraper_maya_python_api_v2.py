# %%
import datetime
import requests
import json
import os
import webbrowser


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
root_url = _getYearQualifiedUrl("https://help.autodesk.com/view/MAYAUL/{year}/ENU/?guid=Maya_SDK_MERGED_py_ref_index_html")
# This is the url prefix used to navigate html files (the Maya docs do not use relative paths)
html_url_prefix = _getYearQualifiedUrl("https://help.autodesk.com/view/MAYAUL/{year}/ENU/?guid=Maya_SDK_MERGED_py_ref_")
# This is the url prefix used to navigate javascript files
js_url_prefix = _getYearQualifiedUrl("https://help.autodesk.com/cloudhelp/{year}/ENU/Maya-SDK-MERGED/py_ref/")
"""
To find the below 'packages_js_url' resource:
    - Load 'root_url'
    - Use the sidebar to expand: Packages -> Packages
    - This will ensure the 'namespaces.js' script is loaded
    - In Chrome: inspect the page -> Select 'Network' tab -> Select 'namespaces.js' -> Select 'Headers' tab
    - Copy the 'Request URL'

The resource allows us to extract a url suffix for each Maya API package which will allow us to navigate to the class list of that package
The resource contains a list of sublists (eg. [ "OpenMaya", "namespace_open_maya.html", null ])
"""
packages_js_url = _getYearQualifiedUrl("https://help.autodesk.com/cloudhelp/{year}/ENU/Maya-SDK-MERGED/py_ref/namespaces.js")


# ----------------------------------------------------------------------------
# --- Private ---
# ----------------------------------------------------------------------------

def _getJSResourceData(request_url):
    """Converts and deserializes the data for a given javascript resource

    The Maya API documentation uses javascript files to dynamically load in data
    Each '.js' file stores data in the same format

    Example:
        var namespaces =
        [
            [ "OpenMaya", "namespace_open_maya.html", null ],
            [ "OpenMayaAnim", "namespace_open_maya_anim.html", null ],
            [ "OpenMayaRender", "namespace_open_maya_render.html", null ],
            [ "OpenMayaUI", "namespace_open_maya_u_i.html", null ]
        ];

    This function will convert the javascript var into a Python list
    The first index always contains an identifier whilst the second index will contain a relative url for that identifier
    """
    # Request the data
    response = requests.get(request_url)
    if response.status_code != 200:
        raise RuntimeError("{} : website does not exist".format(request_url))
    content = response.content

    # Decode the data
    content = content.split("\n", 1)[1].rstrip(";")
    data = json.loads(content)

    return data


def _formatJSResourceData(data, url_prefix, url_suffix):
    """Converts the data returned from _getJSResourceData() into a dictionary mapping identifiers to urls

    As mentioned in _getJSResourceData(), each sublist contains an identifier and a relative url
    This function will form full urls using the relative url of each sublist as well as the url_prefix and url_suffix arguments
    Each full url will be mapped to the respective identifier
    """
    # Create a mapping
    url_mapping = {}

    for sublistData in data:
        key = sublistData[0]
        # Sometimes the javascript resource will contain relative urls suffixed by anchors
        # It will look like <url>.html<anchor>
        url_content, anchor = sublistData[1].rsplit(".html")
        url = url_prefix + url_content + url_suffix + anchor
        url_mapping[key] = url

    return url_mapping


# ----------------------------------------------------------------------------
# --- Public ---
# ----------------------------------------------------------------------------

def getPackageUrlMapping():
    """Return a dictionary mapping Maya API package names to urls
    Each url points to the class list for the corresponding OpenMaya package
    """
    packages_data = _getJSResourceData(packages_js_url)
    package_url_mapping = _formatJSResourceData(packages_data, html_url_prefix, "_html")

    return package_url_mapping


def getPackageUrl(packageName):
    """Return a url pointing to the class list documentation for a given Maya API package

    Args:
        packageName (str): Valid values are
            - OpenMaya
            - OpenMayaAnim
            - OpenMayaRender
            - OpenMayaUI
    """
    return getPackageUrlMapping()[packageName]


def getClassUrlMapping(packageName):
    """Return a dictionary mapping class names for a given Maya API package to urls for the classes documentation"""
    # Get the js urls which provide the class lists for each package
    packages_data = _getJSResourceData(packages_js_url)
    package_classesJsUrl_mapping = _formatJSResourceData(packages_data, js_url_prefix, ".js")
    # Get the class urls for the package
    classes_js_url = package_classesJsUrl_mapping[packageName]
    classes_data = _getJSResourceData(classes_js_url)
    classes_url_mapping = _formatJSResourceData(classes_data, html_url_prefix, "_html")

    return classes_url_mapping


def getClassUrl(packageName, className):
    """Return a url to the documentation of a Maya API class"""
    return getClassUrlMapping(packageName)[className]


def getClassToMembersUrlMapping(packageName):
    """Return a dictionary mapping class names for a given Maya API package to urls pointing to a javascript resource containing member urls"""
    # Get the js urls which provide the class lists for each package
    packages_data = _getJSResourceData(packages_js_url)
    package_classesJsUrl_mapping = _formatJSResourceData(packages_data, js_url_prefix, ".js")
    # Get a dictionary mapping class names to urls which provide the member list for each class
    classes_js_url = package_classesJsUrl_mapping[packageName]
    classes_data = _getJSResourceData(classes_js_url)
    class_membersJsUrl_mapping = _formatJSResourceData(classes_data, js_url_prefix, ".js")

    return class_membersJsUrl_mapping


def getClassMembersUrl(packageName, className):
    """Return a url to a javascript resource containing the member urls of a Maya API class"""
    return getClassToMembersUrlMapping(packageName)[className]


def getClassMembersUrlMapping(packageName, className):
    """Return a dictionary mapping member names for a given Maya API class to urls for the member's documentation"""
    class_members_js_url = getClassMembersUrl(packageName, className)
    # Get a dictionary mapping class member names to urls for each member anchor
    try:
        members_data = _getJSResourceData(class_members_js_url)
    except RuntimeError:
        # Some classes have no members, therefore there is no javascript resource for those classes
        return {}

    members_url_mapping = _formatJSResourceData(members_data, html_url_prefix, "_html")

    return members_url_mapping


def getMemberUrl(packageName, className, memberName):
    """Return a url to the documentation of a Maya API class member"""
    maya_package_class_members_url_mapping = getClassMembersUrlMapping(packageName, className)

    return maya_package_class_members_url_mapping[memberName]


def getGlobalUrlMapping():
    """Return a dictionary containing the urls to every package, class and member in the Maya API documentation

    The aim of this function is to provide a more efficient approach to retrieving a global set of urls

    .. warning::
        This function will run extremely slow

    The structure of the mapping will be as follows:
        mapping = {
            "project": "url",
            "modules": {
                "OpenMaya": "url"
            },
            "classes": {
                "OpenMaya": {
                    "MAngle": "url"
                }
            },
            "members": {
                "OpenMaya": {
                    "MAngle": {
                        "asUnits": "url"
                    }
                }
            }
        }
    """
    global_url_mapping = {"project": root_url}
    global_url_mapping["classes"] = {}
    global_url_mapping["members"] = {}

    packages_data = _getJSResourceData(packages_js_url)
    # Get the package urls which provide the class lists of each package
    package_url_mapping = _formatJSResourceData(packages_data, html_url_prefix, "_html")
    # Get the js urls which provide the class lists for each package
    package_classesJsUrl_mapping = _formatJSResourceData(packages_data, js_url_prefix, ".js")

    global_url_mapping["modules"] = package_url_mapping
    for package in package_url_mapping:
        global_url_mapping["members"][package] = {}

        # Get the class urls for each package
        classes_js_url = package_classesJsUrl_mapping[package]
        classes_data = _getJSResourceData(classes_js_url)
        class_url_mapping = _formatJSResourceData(classes_data, html_url_prefix, "_html")
        global_url_mapping["classes"][package] = class_url_mapping
        # Get the urls to a js resource providing the member data for each class
        class_membersJsUrl_mapping = _formatJSResourceData(classes_data, js_url_prefix, ".js")

        # Get the member urls for each class
        for className in class_url_mapping:
            class_members_js_url = class_membersJsUrl_mapping[className]
            try:
                members_data = _getJSResourceData(class_members_js_url)
            except RuntimeError:
                members_url_mapping = {}
            else:
                members_url_mapping = _formatJSResourceData(members_data, html_url_prefix, "_html")
            global_url_mapping["members"][package][className] = members_url_mapping

    return global_url_mapping


def writeGlobalUrlMapping(fileName="urls_maya_python_api_v2.json"):
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


def browse(url):
    webbrowser.open(url)


# Anchor List Script Example:
"https://help.autodesk.com/cloudhelp/2020/ENU/Maya-SDK-MERGED/py_ref/class_open_maya_1_1_m_angle.js"
# Anchor Example:
"https://help.autodesk.com/view/MAYAUL/2020/ENU/?guid=Maya_SDK_MERGED_py_ref_class_open_maya_1_1_m_angle_html#a934f121109da8c565d519db181690194"


if __name__ == "__main__":
    writeGlobalUrlMapping("..\\data\\urls_maya_python_api_v2.json")

    # print getPackageUrl("OpenMaya")
    # print getPackageUrl("OpenMayaUI")
    # print getClassUrl("OpenMaya", "MVector")
    # print getClassUrl("OpenMayaUI", "MMaterial")
    # print getMemberUrl("OpenMaya", "MDGModifier", "createNode")

    # browse(getMemberUrl("OpenMaya", "MDGModifier", "createNode"))

    # outputPath = os.path.join(os.path.dirname(__file__), "..\\data\\maya_python_api_doc_urls.json")
    # with open(outputPath, 'r') as outputFile:
    #     global_url_mapping = json.load(outputFile)
    #     print global_url_mapping["modules"]["OpenMaya"]
    #     print global_url_mapping["classes"]["OpenMaya"]["MDGModifier"]
    #     print global_url_mapping["members"]["OpenMaya"]["MDGModifier"]["createNode"]

    # %%
