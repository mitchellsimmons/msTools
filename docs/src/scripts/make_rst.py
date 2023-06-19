import os
import sys

PACKAGE_ROOT_PATH = "C:\\dev\\maya\\msTools"
TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

sys.path.append(PACKAGE_ROOT_PATH)

from msTools.core.py import path_utils


def make_rst(dirPath):
    if not os.path.abspath(dirPath).startswith(os.path.abspath(TEMPLATE_PATH) + os.sep):
        return

    for filename in path_utils.iterFiles(dirPath, ext=".py"):
        outputFileName = "msTools"
        head, tail = os.path.split(dirPath)

        while tail and tail != "msTools":
            outputFileName = ".".join([outputFileName, tail])
            head, tail = os.path.split(dirPath)

        outputFileName = outputFileName + ".rst"
        outputFilePath = os.path.join(TEMPLATE_PATH, outputFileName)

        if not os.path.exists(outputFilePath):
            with open(outputFilePath, "w"):
                pass


if __name__ == "__main__":
    # Build rst files for core packages
    make_rst("C:\\dev\\maya\\msTools\\msTools\\core\\maya")
    make_rst("C:\\dev\\maya\\msTools\\msTools\\core\\py")
    make_rst("C:\\dev\\maya\\msTools\\msTools\\coreUI\\maya")
    make_rst("C:\\dev\\maya\\msTools\\msTools\\coreUI\\qt")
