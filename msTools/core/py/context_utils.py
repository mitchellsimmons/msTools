"""
General purpose context managers.

----------------------------------------------------------------
"""


class Null(object):
    """A context manager that returns ``enterResult`` from :meth:`__enter__`, but otherwise does nothing.
    It is intended to be used as a stand-in for an optional context manager.

    Note:
        Designed to resemble `contextlib.nullcontext` which was added in Python 3.7.

    Example:
        .. code-block:: python

            def myfunction(arg, ignore_exceptions=False):
                if ignore_exceptions:
                    # Use Suppress to ignore all exceptions.
                    cm = Suppress(Exception)
                else:
                    # Do not ignore any exceptions, cm has no effect.
                    cm = Null()
                with cm:
                    # Do something
    """

    def __init__(self, enterResult=None):
        self.enterResult = enterResult

    def __enter__(self):
        return self.enterResult

    def __exit__(self, *_):
        pass


class Suppress(object):
    """A context manager that suppresses any of the specified exceptions if they occur in the body of a with statement and then resumes execution with the first statement following the end of the with statement.

    As with any other mechanism that completely suppresses exceptions, this context manager should be used only to cover very specific errors where silently continuing with program execution is known to be the right thing to do.

    Note:
        Designed to resemble `contextlib.suppress` which was added in Python 3.4.

    Example:
        .. code-block:: python

            with suppress(FileNotFoundError):
                os.remove('somefile.tmp')
    """

    def __init__(self, *exceptions):
        self.exceptions = exceptions

    def __enter__(self):
        pass

    def __exit__(self, excType, excVal, excTb):
        if issubclass(excType, self.exceptions):
            return True
