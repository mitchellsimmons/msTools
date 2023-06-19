"""
General purpose utility functions relating to paths.

----------------------------------------------------------------
"""
import os
import subprocess
import sys


# ----------------------------------------------------------------------------
# --- Retrieve ---
# ----------------------------------------------------------------------------

def iterFiles(root, ext=None, walk=False, paths=True):
    """Yield the names or paths of files within the descendant hierarchy of a directory tree.

    Args:
        root (:class:`basestring`): Absolute path specifying the root of a directory tree from which to traverse.
        ext (:class:`basestring`, optional): Specify a specific file extension used to filter results. Defaults to :data:`None` - yield all file extension types.
        walk (:class:`bool`, optional): Whether to walk the entire descendant hierarchy of the directory tree. Defaults to :data:`False`.
        paths (:class:`bool`, optional): If :data:`True`, yield the path to each file, otherwise yield the name of each file. Defaults to :data:`True`.

    Yields:
        :class:`str`: A path or name for each file within the traversed directory tree of ``root``.
    """
    # Each iteration provides the subdirectory and file names at a given level of the directory tree
    for dirpath, dirnames, filenames in os.walk(root):
        for filename in filenames:
            if not ext or filename.endswith(ext):
                if paths:
                    yield os.path.join(dirpath, filename)
                else:
                    yield filename

        # We can exit the loop after the first iteration to prevent searching sub-directories
        if not walk:
            break


def iterDirectories(root, walk=False, paths=True):
    """Yield the names or paths of directories within the descendant hierarchy of a directory tree.

    Args:
        root (:class:`basestring`): Absolute path specifying the root of a directory tree from which to traverse.
        walk (:class:`bool`, optional): Whether to walk the entire descendant hierarchy of the directory tree. Defaults to :data:`False`.
        paths (:class:`bool`, optional): If :data:`True`, yield the path to each directory, otherwise yield the name of each directory. Defaults to :data:`True`.

    Yields:
        :class:`str`: A path or name for each directory within the traversed directory tree of ``root``.
    """
    # Each iteration provides the subdirectory and file names at a given level of the directory tree
    for dirpath, dirnames, filenames in os.walk(root):
        for dirname in dirnames:
            if paths:
                yield os.path.join(dirpath, dirname)
            else:
                yield dirname

        # We can exit the loop after the first iteration to prevent searching sub-directories
        if not walk:
            break


# ----------------------------------------------------------------------------
# --- Open ---
# ----------------------------------------------------------------------------

def openFile(path):
    """Opens a file or folder at the given path."""
    if os.name == "nt":
        os.startfile(path)
    elif sys.platform.startswith("linux"):
        subprocess.call(["xdg-open", path])
    elif sys.platform.startswith("darwin"):
        subprocess.call(["open", path])
    else:
        raise OSError("Unsupported platform '{}'".format(os.name))
