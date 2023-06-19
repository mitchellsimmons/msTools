import json
import os

from msTools.vendor.enum import Enum
from msTools.vendor.Qt import QtCore, QtGui


class UrlProxyModel(QtCore.QSortFilterProxyModel):

    def __init__(self):
        super(UrlProxyModel, self).__init__()

        self.setSourceModel(UrlModel())

    @property
    def source(self):
        return self.sourceModel()

    def getSourceItem(self, proxyIndex):
        sourceIndex = self.mapToSource(proxyIndex)
        return self.source.itemFromIndex(sourceIndex)

    def getSourceDataTree(self, proxyIndex, role=QtCore.Qt.DisplayRole):
        dataTree = []
        sourceIndex = self.mapToSource(proxyIndex)

        while sourceIndex.isValid():
            dataTree.insert(0, self.source.data(sourceIndex, role=role))
            sourceIndex = sourceIndex.parent()

        return dataTree

    def filterAcceptsRow(self, sourceRow, sourceParent):
        sourceIndex = self.source.index(sourceRow, 0, sourceParent)
        columnType = self.source.data(sourceIndex, role=UrlModel.Role.COLUMN_TYPE)

        # Only display a project or module if there is a class to display
        if columnType == UrlModel.ColumnType.PROJECT or columnType == UrlModel.ColumnType.MODULE:
            rowCount = self.source.rowCount(sourceIndex)
            for rowIndex in range(rowCount):
                if self.filterAcceptsRow(rowIndex, sourceIndex):
                    return True
            return False

        filterPattern = self.filterRegExp().pattern()
        filterPatterTokens = filterPattern.split(".")
        itemText = self.source.data(sourceIndex, role=QtCore.Qt.DisplayRole)

        if columnType == UrlModel.ColumnType.CLASS:
            if len(filterPatterTokens) >= 2:
                # If there is a member token, only show the class if there is a matching member
                if filterPatterTokens[-2] in itemText:
                    rowCount = self.source.rowCount(sourceIndex)
                    for rowIndex in range(rowCount):
                        if self.filterAcceptsRow(rowIndex, sourceIndex):
                            return True
            elif filterPatterTokens[-1] in itemText:
                return True
        elif columnType == UrlModel.ColumnType.MEMBER:
            # Show members by default if there is only a single token (ie. class filter)
            if len(filterPatterTokens) >= 2:
                if filterPatterTokens[-1] in itemText:
                    return True
            else:
                return True

        return False


class UrlModel(QtGui.QStandardItemModel):

    _DATA_RESOURCES = {
        "Maya Python API 2.0": os.path.abspath(os.path.join(__file__, "..\\..\\resources\\data\\mayaApiDoc_urls.json")),
        "Maya Python Commands": os.path.abspath(os.path.join(__file__, "..\\..\\resources\\data\\mayaCmdsDoc_urls.json")),
        "PySide2": os.path.abspath(os.path.join(__file__, "..\\..\\resources\\data\\PySide2Doc_urls.json")),
    }

    class Role(object):
        URL = QtCore.Qt.UserRole + 1
        ANCHOR_ID = QtCore.Qt.UserRole + 2
        COLUMN_TYPE = QtCore.Qt.UserRole + 3

    class ColumnType(Enum):
        PROJECT = 0
        MODULE = 1
        CLASS = 2
        MEMBER = 3

    def __init__(self):
        super(UrlModel, self).__init__()

        self._data = {}
        self._loadData()

        self._appendOpenMayaData()
        self._appendCmdsData()
        self._appendPySideData()

    # --- Private ----------------------------------------------------------------------------

    def _loadData(self):
        for resourceName, resourcePath in UrlModel._DATA_RESOURCES.items():
            with open(resourcePath, 'r') as resourceFile:
                self._data[resourceName] = json.load(resourceFile)

    def _appendOpenMayaData(self):
        rootItem = self.invisibleRootItem()

        projectItem = QtGui.QStandardItem("Maya Python API 2.0")
        projectItem.setData(UrlModel.ColumnType.PROJECT, role=UrlModel.Role.COLUMN_TYPE)
        projectItem.setData(self._data["Maya Python API 2.0"]["project"], role=UrlModel.Role.URL)
        rootItem.appendRow(projectItem)

        for moduleName, moduleUrl in sorted(self._data["Maya Python API 2.0"]["modules"].items()):
            moduleItem = QtGui.QStandardItem(moduleName)
            moduleItem.setData(UrlModel.ColumnType.MODULE, role=UrlModel.Role.COLUMN_TYPE)
            moduleItem.setData(moduleUrl, role=UrlModel.Role.URL)
            projectItem.appendRow(moduleItem)

            for className, classUrl in sorted(self._data["Maya Python API 2.0"]["classes"][moduleName].items()):
                classItem = QtGui.QStandardItem(className)
                classItem.setData(UrlModel.ColumnType.CLASS, role=UrlModel.Role.COLUMN_TYPE)
                classItem.setData(classUrl, role=UrlModel.Role.URL)
                moduleItem.appendRow(classItem)

                for memberName, memberUrl in sorted(self._data["Maya Python API 2.0"]["members"][moduleName][className].items()):
                    memberUrlTokens = memberUrl.split("#")
                    memberItem = QtGui.QStandardItem(memberName)
                    memberItem.setData(UrlModel.ColumnType.MEMBER, role=UrlModel.Role.COLUMN_TYPE)
                    memberItem.setData(memberUrlTokens[0], role=UrlModel.Role.URL)
                    if len(memberUrlTokens) == 2:
                        memberItem.setData(memberUrlTokens[1], role=UrlModel.Role.ANCHOR_ID)
                    classItem.appendRow(memberItem)

    def _appendCmdsData(self):
        rootItem = self.invisibleRootItem()

        projectItem = QtGui.QStandardItem("Maya Python Commands")
        projectItem.setData(UrlModel.ColumnType.PROJECT, role=UrlModel.Role.COLUMN_TYPE)
        projectItem.setData(self._data["Maya Python Commands"]["project"], role=UrlModel.Role.URL)
        rootItem.appendRow(projectItem)

        for commandName, commandUrl in sorted(self._data["Maya Python Commands"]["commands"].items()):
            commandItem = QtGui.QStandardItem(commandName)
            commandItem.setData(UrlModel.ColumnType.CLASS, role=UrlModel.Role.COLUMN_TYPE)
            commandItem.setData(commandUrl, role=UrlModel.Role.URL)
            projectItem.appendRow(commandItem)

    def _appendPySideData(self):
        rootItem = self.invisibleRootItem()

        projectItem = QtGui.QStandardItem("PySide2")
        projectItem.setData(UrlModel.ColumnType.PROJECT, role=UrlModel.Role.COLUMN_TYPE)
        projectItem.setData(self._data["PySide2"]["project"], role=UrlModel.Role.URL)
        rootItem.appendRow(projectItem)

        for moduleName, moduleUrl in sorted(self._data["PySide2"]["modules"].items()):
            moduleItem = QtGui.QStandardItem(moduleName)
            moduleItem.setData(UrlModel.ColumnType.MODULE, role=UrlModel.Role.COLUMN_TYPE)
            moduleItem.setData(moduleUrl, role=UrlModel.Role.URL)
            projectItem.appendRow(moduleItem)

            for className, classUrl in sorted(self._data["PySide2"]["classes"][moduleName].items()):
                classItem = QtGui.QStandardItem(className)
                classItem.setData(UrlModel.ColumnType.CLASS, role=UrlModel.Role.COLUMN_TYPE)
                classItem.setData(classUrl, role=UrlModel.Role.URL)
                moduleItem.appendRow(classItem)

                for memberName, memberUrl in sorted(self._data["PySide2"]["members"][moduleName][className].items()):
                    memberUrlTokens = memberUrl.split("#")
                    memberItem = QtGui.QStandardItem(memberName)
                    memberItem.setData(UrlModel.ColumnType.MEMBER, role=UrlModel.Role.COLUMN_TYPE)
                    memberItem.setData(memberUrlTokens[0], role=UrlModel.Role.URL)
                    if len(memberUrlTokens) == 2:
                        memberItem.setData(memberUrlTokens[1], role=UrlModel.Role.ANCHOR_ID)
                    classItem.appendRow(memberItem)
