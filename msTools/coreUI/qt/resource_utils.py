"""
Utility functions for dealing with :doc:`The Qt Resource System <PySide2:overviews/resources>`.

----------------------------------------------------------------
"""
import logging
import os
import subprocess
log = logging.getLogger(__name__)

from msTools.core.py import path_utils as PY_PATH


# ----------------------------------------------------------------------------
# --- Build Resource Collection ---
# ----------------------------------------------------------------------------

@log.timeit(logging.DEBUG)
def buildResourceCollection(resourcesDirPath, fileName="resources"):
    """Build a `Qt`_ Resource Collection file from a `resources` directory.

    - All icon resources must be located within the directory tree rooted at `resources/icons`.
    - All OpenType Font files must be located within the directory tree rooted at `resources/otfs`.

    The `Qt`_ Resource Collection file will be output to the given `resources` directory.

    Args:
        resourcesDirPath (:class:`basestring`): Path to a directory named `resources` from which to build a `qrc` file.
        fileName (:class:`basestring`, optional): Name to give the resulting `Qt`_ Resource Collection file. Defaults to ``"resources"``.

    Raises:
        :exc:`~exceptions.ValueError`: If the ``resourcesDirPath`` does not reference a valid directory whose base name is `resources`.
    """
    resourcesDirName = os.path.basename(resourcesDirPath)
    resourcesFilePath = os.path.join(resourcesDirPath, fileName + ".qrc")

    if not resourcesDirName == "resources":
        raise ValueError("Expected a path to a directory named 'resources' from which to query resource files")

    iconsDirPath = os.path.join(resourcesDirPath, "icons")
    otfsDirPath = os.path.join(resourcesDirPath, "otfs")

    with open(resourcesFilePath, "w") as f:
        f.write('<!DOCTYPE RCC><RCC version="1.0">\n<qresource>\n')

    if os.path.exists(iconsDirPath):
        with open(resourcesFilePath, "a") as f:
            for iconFilePath in PY_PATH.iterFiles(iconsDirPath, walk=True):
                relativeIconFilePath = os.path.relpath(iconFilePath, resourcesDirPath)
                f.write('   <file>' + relativeIconFilePath.replace('\\', '/') + '</file>\n')
    else:
        log.debug("Unable to locate any icon resources, 'icons' sub-directory does not exist")

    if os.path.exists(otfsDirPath):
        with open(resourcesFilePath, "a") as f:
            for otfFilePath in PY_PATH.iterFiles(otfsDirPath, ext="otf", walk=True):
                relativeOtfFilePath = os.path.relpath(otfFilePath, resourcesDirPath)
                f.write('   <file>' + relativeOtfFilePath.replace('\\', '/') + '</file>\n')
    else:
        log.debug("Unable to locate any otf resources, 'otfs' sub-directory does not exist")

    with open(resourcesFilePath, "a") as f:
        f.write('</qresource>\n</RCC>')


# ----------------------------------------------------------------------------
# --- Compile Resource Collection ---
# ----------------------------------------------------------------------------

@log.timeit(logging.DEBUG)
def compileResourceCollection(resourceFilePath, compilerPath, fileName="binary_resources"):
    """Compile binary data from a `Qt`_ Resource Collection file.

    Bytecode is output to a Python module in the same directory as the given `Qt`_ Resource Collection file.

    Args:
        resourceFilePath (:class:`basestring`): Path to a `Qt`_ Resource Collection file from which to compile binary data.
        compilerPath (:class:`basestring`): Path to a `Qt`_ Resource compiler, usually named something like `pyside2-rcc.exe` or `pyrcc5`, depending on your target `Qt`_ Python bindings.
        fileName (:class:`basestring`, optional): Name to give the resulting Python module. Defaults to ``"binary_resources"``.

    Raises:
        :exc:`~exceptions.ValueError`: If the ``resourceFilePath`` does not reference a valid `Qt`_ Resource Collection file.
        :exc:`~exceptions.ValueError`: If the ``compilerPath`` does not reference a valid `Qt`_ Resource compiler.
        :exc:`~exceptions.RuntimeError`: If there was an issue generating the binary data from the `Qt`_ Resource Collection file.
    """
    _, resourceFileExt = os.path.splitext(resourceFilePath)
    resourcesDirPath = os.path.dirname(resourceFilePath)
    outputFilePath = os.path.join(resourcesDirPath, fileName + ".py")

    if not os.path.exists(resourceFilePath) or resourceFileExt != ".qrc":
        raise ValueError("{}: File path does not reference a valid Qt Resource Collection file")

    _, compilerExt = os.path.splitext(compilerPath)

    if not os.path.exists(compilerPath) or compilerExt != ".exe":
        raise ValueError("{}: File path does not reference a valid Qt Resource Compiler")

    # If shell=False, any error that has a non-zero exit status will be raised immediately by the current interpreter
    process = subprocess.Popen(r'"{}" -o "{}" "{}"'.format(compilerPath, outputFilePath, resourceFilePath), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, error = process.communicate()

    if process.returncode != 0:
        raise RuntimeError(error)
    elif error:
        # Non-critical errors can still occur with a zero exit status (usually for missing files)
        for line in error.splitlines():
            log.info(line)
