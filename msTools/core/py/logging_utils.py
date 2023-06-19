"""
General purpose logging objects.

----------------------------------------------------------------

:class:`logging.Logger`
-----------------------

    Responsible for creating and processing log records.
    Instantiated with a call to :func:`logging.getLogger` using the name of a module.

    - Passing the ``__name__`` attribute of a module will return a logger for that module.
    - Not passing a name will return the root logger.

    Each module logger is a descendant of the root logger.
    Messages from descendant loggers are propagated upstream through the hierarchy of ancestral loggers.
    Propagation of messages can be disabled via the :attr:`logging.Logger.propagate` property.

    Any logger which has a handler will format the message and output it to a stream or file depending on the type of handler.

----------------------------------------------------------------

:class:`logging.StreamHandler`
------------------------------

    Responsible for sending log records to streams such as :data:`sys.stdout` or :data:`sys.stderr`.
    A handler can be added to a logger via :meth:`logging.Logger.addHandler`.

----------------------------------------------------------------

:class:`logging.Formatter`
--------------------------

    Responsible for formatting the layout of log records before outputting to the final destination.
    They determine what information should be logged.
    A formatter can be set to a handler with :meth:`logging.Handler.setFormatter`.

----------------------------------------------------------------

:class:`logging.Filter`
-----------------------

    Provide the ability to filter log records received by a handler.
    A filter can be added to a handler with :meth:`logging.Handler.addFilter`.

----------------------------------------------------------------
"""
import logging
import time

from msTools.vendor import decorator


# ----------------------------------------------------------------------------
# --- Classes ---
# ----------------------------------------------------------------------------

class Logger(logging.getLoggerClass()):
    """Extends the functionality of the current logger class by inheriting from the result of :func:`logging.getLoggerClass`.

    The resulting class must be set using :func:`logging.setLoggerClass` in order for :func:`logging.getLogger` to return instances of this class.
    """

    def timeit(self, level):
        """Decorator factory for producing a decorator which will time a decorated function and log a record of the result.

        Args:
            level (:class:`int`): A level constant from :class:`logging.Logger` representing the level at which to log the timing message.
                Possible attributes are `NOTSET`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

        Example:
            .. code-block:: python

                logger = logging.getLogger(__name__)

                @logger.timeit(logging.DEBUG)
                def foo():
                    time.sleep(2)

                # Produces a logging output which details the running time of the `foo` call
                foo()
        """
        def timed(func, *args, **kwargs):
            start = time.clock()
            result = func(*args, **kwargs)
            end = time.clock()
            delta = (end - start)
            self.log(level, "func:{!r} args:[{!r}, {!r}] took: {:.3f} sec".format(func.__name__, args, kwargs, delta))
            return result

        return decorator.decorator(timed)

    def makeRecord(self, *args, **kwargs):
        """Extends the functionality of :class:`logging.LogRecord` objects produces by instances of this logger.

        The following attributes are added to :class:`logging.LogRecord` objects and can be used to format the layout of the final output.

        - ``funcNameLineno``: Uses format `%(funcNameLineno)s`. Produces output `funcName:lineno`.
        - ``nameFuncNameLineno``: Uses format `%(nameFuncNameLineno)s`. Produces output `name - funcName:lineno`.
        - ``levelNameFuncNameLineno``: Uses format `%(levelNameFuncNameLineno)s`. Produces output `levelname - funcName:lineno`.
        """
        record = super(Logger, self).makeRecord(*args, **kwargs)

        # funcName:lineno
        record.funcNameLineno = ":".join([record.funcName, str(record.lineno)])

        # name - funcName:lineno
        record.nameFuncNameLineno = " - ".join([record.name, record.funcNameLineno])

        # levelname - funcName:lineno
        record.levelNameFuncNameLineno = " - ".join([record.levelname, record.funcNameLineno])

        return record


class NoParsingFilter(logging.Filter):
    """A :class:`logging.Filter` subclass used to prevent a handler from processing :class:`logging.LogRecord` objects from certain loggers."""

    def __init__(self, filterNamePrefix, *args, **kwargs):
        """Initialise the filter.

        Args:
            filterNamePrefix (:class:`basestring`): Used to filter :class:`logging.LogRecord` objects.
                If the `name` attribute starts with this prefix, the handler to which this filter is assigned will not process the record.
        """
        self._filterNamePrefix = filterNamePrefix
        super(NoParsingFilter, self).__init__(*args, **kwargs)

    def filter(self, record):
        """Override of :meth:`logging.Filter.filter`. Filters based on the initialised prefix."""
        return not record.name.startswith(self._filterNamePrefix)
