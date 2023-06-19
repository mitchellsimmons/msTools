.. msTools documentation master file, created by
   sphinx-quickstart on Wed Apr 08 09:54:08 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.


Welcome to msTools's documentation!
***********************************


----


Structure
=========

   The :doc:`msTools <../index>` package is split into multiple sub-packages containing either core or specialised functionality.
   Core functionality is split between the `msTools.core`_ and `msTools.coreUI`_ sub-packages. Both provide low-level abstractions for various APIs.
   Specialised packages such as `msTools.tools`_ and `msTools.metadata`_ are dependant upon core functionality but have a higher-level objective.


Guidelines
==========

   1. Operations will preference throwing an exception over returning a null `OpenMaya`_ object.
   2. Operations will assume the internal Maya object of any `OpenMaya`_ input is valid.
   3. Operations will raise a :exc:`msTools.core.maya.exceptions.MayaTypeError` for any exceptional behaviour relating to the internal type of Maya objects.
      This attempts to homogenise the behaviour of the `OpenMaya`_ API which raises :exc:`~exceptions.TypeError` or :exc:`~exceptions.RuntimeError` for different object types.


Syntax
======

   | This documentation makes use of a legacy approach to specifying types since static type checking was implemented in `Python 3.5 <https://docs.python.org/3.5>`_ (see `typing <https://docs.python.org/3/library/typing.html>`_ module), whilst :doc:`msTools <../index>` is confined to `Python 2.7 <https://docs.python.org/2.7>`_.
   | Because there is no standard type syntax for this legacy approach, use of the `PyCharm type syntax <https://www.jetbrains.com/help/pycharm/type-syntax-for-docstrings.html>`_ is adopted with the following amendments:

   .. list-table::
      :widths: 30 70
      :header-rows: 1

      * - Syntax
        - Description
      * - ``any``
        - Argument of any type.
      * - ``Foo, optional``
        - Argument of type ``Foo`` which has a default value assigned.
      * - ``callable[[Foo, Bar], Bar]``
        - A callable with two arguments ``[Foo, Bar]`` and return type ``Bar``.
      * - ``callable[..., Bar]``
        - A callable with any call signature and return type ``Bar``.
      * - ``iterable[Foo]``
        - Any iterable type containing elements of type ``Foo``.
      * - ``(Foo, Bar)``
        - A :obj:`tuple` of two elements whose types are ``Foo`` and ``Bar`` respectively.
      * - ``(Foo, ...)``
        - A variable length :obj:`tuple` containing elements of type ``Foo``.
      * - ``T <= Foo``
        - Argument of type ``T`` with upper bound ``Foo``, meaning ``T`` is a (non-strict) subclass of ``Foo``.

   .. note:: If an ``optional`` argument of type ``Foo`` accepts a default value of :data:`None` this will be mentioned in the description
      as opposed to displaying a union of types ``Foo | None``.


----


msTools.core
============

   | Contains non-UI related functionality.

   .. toctree::
      :caption: msTools.core.maya
      :maxdepth: 1

      /templates/msTools.core.maya.attribute_utils
      /templates/msTools.core.maya.callback_utils
      /templates/msTools.core.maya.component_utils
      /templates/msTools.core.maya.constants
      /templates/msTools.core.maya.context_utils
      /templates/msTools.core.maya.dag_utils
      /templates/msTools.core.maya.decorator_utils
      /templates/msTools.core.maya.dg_utils
      /templates/msTools.core.maya.exceptions
      /templates/msTools.core.maya.inspect_utils
      /templates/msTools.core.maya.math_utils
      /templates/msTools.core.maya.name_utils
      /templates/msTools.core.maya.om_utils
      /templates/msTools.core.maya.plug_utils
      /templates/msTools.core.maya.reference_utils
      /templates/msTools.core.maya.shader_utils
      /templates/msTools.core.maya.uuid_utils

   .. toctree::
      :caption: msTools.core.py
      :maxdepth: 1

      /templates/msTools.core.py.class_utils
      /templates/msTools.core.py.context_utils
      /templates/msTools.core.py.decorator_utils
      /templates/msTools.core.py.logging_utils
      /templates/msTools.core.py.metaclasses
      /templates/msTools.core.py.module_utils
      /templates/msTools.core.py.path_utils
      /templates/msTools.core.py.structures


----


msTools.coreUI
==============

   | Contains UI related functionality.

   .. toctree::
      :caption: msTools.coreUI.maya
      :maxdepth: 1

      /templates/msTools.coreUI.maya.exceptions
      /templates/msTools.coreUI.maya.inspect_utils
      /templates/msTools.coreUI.maya.nodeEditor_utils
      /templates/msTools.coreUI.maya.widget_utils

   .. toctree::
      :caption: msTools.coreUI.qt
      :maxdepth: 1

      /templates/msTools.coreUI.qt.animation_utils
      /templates/msTools.coreUI.qt.application_utils
      /templates/msTools.coreUI.qt.constants
      /templates/msTools.coreUI.qt.context_utils
      /templates/msTools.coreUI.qt.event_utils
      /templates/msTools.coreUI.qt.graphicsItem_utils
      /templates/msTools.coreUI.qt.inspect_utils
      /templates/msTools.coreUI.qt.resource_utils
      /templates/msTools.coreUI.qt.shape_utils
      /templates/msTools.coreUI.qt.widget_utils


----


msTools.metadata
================

   .. toctree::
      :caption: msTools.metadata.systems
      :maxdepth: 1

      /templates/msTools.metadata.systems.base


----


msTools.tools
=============

   .. toctree::
      :caption: msTools.tools
      :maxdepth: 1

      /templates/msTools.tools.callback_manager
      /templates/msTools.tools.tool_manager
      /templates/msTools.tools.uuid_manager

   .. toctree::
      :caption: msTools.tools.docExplorer
      :maxdepth: 1

      /templates/msTools.tools.docExplorer.main_setup
      /templates/msTools.tools.docExplorer.maya_setup

   .. toctree::
      :caption: msTools.tools.nodeEditorExtensions
      :maxdepth: 1

      /templates/msTools.tools.nodeEditorExtensions.alignNodeTool_setup
      /templates/msTools.tools.nodeEditorExtensions.backgroundOptimisation_manager
      /templates/msTools.tools.nodeEditorExtensions.createNodeTool_setup
      /templates/msTools.tools.nodeEditorExtensions.importExportTool_setup
      /templates/msTools.tools.nodeEditorExtensions.layoutTool_setup
      /templates/msTools.tools.nodeEditorExtensions.maintainLayout_manager
      /templates/msTools.tools.nodeEditorExtensions.menu_setup
      /templates/msTools.tools.nodeEditorExtensions.nodeGraphEditorInfo_manager
      /templates/msTools.tools.nodeEditorExtensions.setup
      /templates/msTools.tools.nodeEditorExtensions.sceneActivation_manager
      /templates/msTools.tools.nodeEditorExtensions.shakeToDisconnect_manager

   .. toctree::
      :caption: msTools.tools.menu
      :maxdepth: 1

      /templates/msTools.tools.menu.setup


----


Importing
=========

   | To import a module simply follow its subpackage path:

   .. code-block:: python

      from msTools.core.maya import plug_utils


----


Indices and tables
==================

   * :ref:`genindex`
   * :ref:`modindex`
   * :ref:`search`

..
   You can search for unicode symbols here:
      https://www.compart.com/en/unicode/
      https://www.w3.org/2003/entities/xml/dbk.xml

   To include in an .rst file, use format:
      .. |xrarr|    unicode:: U+027F6 .. LONG RIGHTWARDS ARROW