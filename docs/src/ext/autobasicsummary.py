"""
As the name suggests this directive is based upon the ``autosummary`` directive.
Its aim is to provide a basic implementation of autosummary (ie. without signatures and summaries).

Options
-------

The directive produces a single column table based on four primary options:

- ``data`` : A flag option which uses the ``currentmodule`` directive to list data members (module-level variables)
- ``functions`` : A flag option which uses the ``currentmodule`` directive to list function members (module-level functions)
- ``attributes`` : A required argument option which expects the name of a class (including nested/outer classes).
  The ``currentmodule`` directive is used to return a class object relative to the module and list attribute members.
- ``classes`` : A required argument option which expects the name of a class (including nested/outer classes).
  The ``currentmodule`` directive is used to return a class object relative to the module and list class members.
  Class members may include nested classes or class objects assigned to attributes (these are not handled by ``attributes``).
- ``methods`` : A required argument option which expects the name of a class (including nested/outer classes).
  The ``currentmodule`` directive is used to return a class object relative to the module and list method members.

The following secondary options are used to filter which member names are included for each primary option:

- ``members`` : An optional argument option that specifies which non-private members will be included.
  If no argument is given, all non-private members will be included.
- ``inherited-members`` : A flag option that signals inherited members should be included.
- ``special-members`` : An optional argument option that specifies which special members will be included.
  If no argument is given, all special members (ie. those starting and ending with ``'__'``) will be included.
  If an argument is given and the ``private-members`` option is provided with no argument, this option will be ignored and all special members will be included.
- ``private-members`` : An optional argument option that specifies which private members will be included.
  If no argument is given, all private members (ie. those starting with ``'_'`` or ``'__'``) will be included.
- ``exclude-members`` : An optional argument option that specifies which members will be excluded (effects all member options).
  If no argument is given, all members will be excluded.

The following options affect the rendered result:

- ``title`` : A required argument option that adds a title to the table.
- ``member-order`` : A required argument option that specifies how members should be ordered. Valid values are:

   * 'alphabetical' (default) : Members will be ordered alphabetically.
   * 'groupwise' :  : Members will be ordered alphabetically by group (based on the ``autobasicsummary_member_type_order`` config value).
   * 'bysource' : Members will retain the source file order.

- ``add-prefix`` : A flag option that adds a prefix to each member (eg. 'def' for functions and methods).

The following options can be used to override default config values.

- ``no-add-prefix``
- ``no-members``
- ``no-inherited-members``
- ``no-special-members``
- ``no-private-members``
- ``no-exclude-members``

Defaults
--------

The following options can be provided default values via the ``autobasicsummary_default_options`` config value (dictionary).

- ``member-order``
- ``add-prefix``
- ``members``
- ``inherited-members``
- ``special-members``
- ``private-members``
- ``exclude-members``
"""

from typing import List, cast

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import ViewList

from sphinx import addnodes
from sphinx.pycode import ModuleAnalyzer, PycodeError
from sphinx.util.inspect import safe_getattr
from sphinx.util.docutils import SphinxDirective
from sphinx.ext.autodoc import get_documenters, DataDocumenter
from sphinx.ext.autodoc.directive import DocumenterBridge, Options


class Config:

    config_values = {
        'autobasicsummary_default_options': (
            {
                'member-order': 'alphabetical',
                'add-prefix': False,
                'members': False,
                'inherited-members': False,
                'special-members': False,
                'private-members': False,
                'exclude-members': False,
            }, 'env'),
        'autobasicsummary_member_type_order': (
            {
                "data": 0,
                "function": 10,
                "attribute": 20,
                "class": 30,
                "method": 40,
            }, 'env'),
    }

    def __init__(self, **settings):
        for name, (default, rebuild) in self.config_values.items():
            setattr(self, name, default)
        for name, value in settings.items():
            setattr(self, name, value)


def setup(app):
    app.add_node(autobasicsummary,
                 html=(autobasicsummary_visit_html, autobasicsummary_noop),
                 latex=(autobasicsummary_noop, autobasicsummary_noop),
                 text=(autobasicsummary_noop, autobasicsummary_noop),
                 man=(autobasicsummary_noop, autobasicsummary_noop),
                 texinfo=(autobasicsummary_noop, autobasicsummary_noop))

    app.add_directive('autobasicsummary', AutoBasicSummaryDirective)

    for name, (default, rebuild) in Config.config_values.items():
        app.add_config_value(name, default, rebuild)


class autobasicsummary(nodes.comment):
    pass


def autobasicsummary_noop(self, node):
    pass


def autobasicsummary_visit_html(self, node):
    """Sourced directly from: autosummary
    https://github.com/sphinx-doc/sphinx/blob/3.x/sphinx/ext/autosummary/__init__.py
    """
    try:
        table = cast(nodes.table, node[0])
        tgroup = cast(nodes.tgroup, table[0])
        tbody = cast(nodes.tbody, tgroup[-1])
        rows = cast(List[nodes.row], tbody)
        for row in rows:
            col1_entry = cast(nodes.entry, row[0])
            par = cast(nodes.paragraph, col1_entry[0])
            for j, subnode in enumerate(list(par)):
                if isinstance(subnode, nodes.Text):
                    new_text = subnode.astext().replace(" ", "\u00a0")
                    par[j] = nodes.Text(new_text)
    except IndexError:
        pass


class AutoBasicSummaryDirective(SphinxDirective):

    # defines the parameter the directive expects
    # directives.unchanged means you get the raw value from RST
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = False
    has_content = True
    option_spec = {
        'title': directives.unchanged_required,
        'member-order': directives.unchanged_required,
        'add-prefix': directives.flag,
        'members': directives.unchanged,
        'inherited-members': directives.flag,
        'special-members': directives.unchanged,
        'private-members': directives.unchanged,
        'exclude-members': directives.unchanged,
        'no-add-prefix': directives.flag,
        'no-members': directives.flag,
        'no-inherited-members': directives.flag,
        'no-special-members': directives.flag,
        'no-private-members': directives.flag,
        'no-exclude-members': directives.flag,
        'data': directives.flag,
        'functions': directives.flag,
        'attributes': directives.unchanged_required,
        'classes': directives.unchanged_required,
        'methods': directives.unchanged_required, }

    _member_type_role_mapping = {
        'data': 'data',
        'function': 'func',
        'attribute': 'attr',
        'class': 'class',
        'method': 'meth',
    }

    _member_orders = ['alphabetical', 'groupwise', 'bysource']

    def get_options(self):
        """Returns a :class:`dict` containing the current directive options.
        Default values for the following options will be included if they do not exist in the current directive options:
        ``add-prefix``, ``inherited-members``, ``special-members``, ``private-members``."""
        default_options = Config.config_values['autobasicsummary_default_options'][0]

        user_options = {
            'member-order': self.env.config['autobasicsummary_default_options'].get('member-order', default_options['member-order']),
            'add-prefix': self.env.config['autobasicsummary_default_options'].get('add-prefix', default_options['add-prefix']),
            'members': self.env.config['autobasicsummary_default_options'].get('members', default_options['members']),
            'inherited-members': self.env.config['autobasicsummary_default_options'].get('inherited-members', default_options['inherited-members']),
            'special-members': self.env.config['autobasicsummary_default_options'].get('special-members', default_options['special-members']),
            'private-members': self.env.config['autobasicsummary_default_options'].get('private-members', default_options['private-members']),
            'exclude-members': self.env.config['autobasicsummary_default_options'].get('exclude-members', default_options['exclude-members']),
        }

        user_options.update(self.options)
        return user_options

    def get_flag_option(self, option):
        """Returns True if the ``option`` exists and is not ``False`` and the associated ``no-<option>`` does not exist."""
        return self.get_options().get(option, False) is not False and "-".join(['no', option]) not in self.options

    def get_arg_option(self, option):
        """Returns the ``option`` argument if the ``option`` exists and was assigned a :class:`str` and the associated ``no-<option>`` does not exist.
        Otherwise returns ``True`` if the ``option`` is not ``False`` and the associated ``no-<option>`` does not exist"""
        options = self.get_options()
        val = options.get(option, False)
        if val and isinstance(val, basestring):
            return val if "-".join(['no', option]) not in self.options else False
        else:
            return val is not False and "-".join(['no', option]) not in self.options

    def run(self):
        self.bridge = DocumenterBridge(self.env, self.state.document.reporter,
                                       Options(), self.lineno)

        self.current_module_name = self.env.ref_context.get('py:module')
        if self.current_module_name is None:
            raise RuntimeError("`currentmodule::` directive must be set.")
        mod = __import__(self.current_module_name, globals(), locals(), [None])

        items = []

        if 'data' in self.options:
            items += self.get_items(mod, 'data')

        if 'functions' in self.options:
            items += self.get_items(mod, 'function')

        if 'attributes' in self.options:
            self.current_class_name = self.options['attributes']
            cls = self.get_class(mod, self.current_class_name)
            items += self.get_items(cls, 'attribute')

        if 'classes' in self.options:
            self.current_class_name = self.options['classes']
            cls = self.get_class(mod, self.current_class_name)
            items += self.get_items(cls, 'class')

        if 'methods' in self.options:
            self.current_class_name = self.options['methods']
            cls = self.get_class(mod, self.current_class_name)
            items += self.get_items(cls, 'method')

        self.order_items(items)

        title = self.options.get('title')
        nodes = self.get_table(items, title=title)

        return nodes

    @staticmethod
    def get_class(mod, class_name):
        """Returns a class with the given ``class_name`` from the given module object.
        If the class is nested the ``class_name`` must include all outer class names.
        """
        tokens = class_name.split(".")
        parent = mod
        for token in tokens:
            cls = getattr(parent, token)
            parent = cls

        return parent

    def get_items(self, obj, member_type):
        """Generates a list of four element tuples containing:

        #. A prefix.
        #. Member name relative to the current module (including any nestes/outer classes).
        #. Member name including the current module (including any nestes/outer classes).
        #. Member type.

        Each item corresponds to the given ``obj`` and ``member_type``:

        - If ``obj`` is a module, ``member_type`` is either ``'data'`` or ``'function'``.
        - If ``obj`` is a class, ``member_type`` is either ``'attribute'`` or ``'method'``.
        """
        add_prefix = self.get_flag_option('add-prefix')
        include_inherited = self.get_flag_option('inherited-members')

        items = []
        names = self.filter_names(dir(obj) if include_inherited else obj.__dict__.keys())

        if member_type == "function":
            # NOTE: module-level functions will always produce a MethodDocumenter and FunctionDocumenter
            # - MethodDocumenter has a higher priority (required for staticmethods) therefore we must accept it
            autodoc_member_type = "method"
        elif member_type == "data":
            # NOTE: module-level variables will always produce an AttributeDocumenter
            autodoc_member_type = "attribute"
        else:
            autodoc_member_type = member_type

        for name in names:
            try:
                member = safe_getattr(obj, name)
            except AttributeError:
                continue

            classes = [doccls for doccls in get_documenters(self.env.app).values()
                       if doccls.can_document_member(member, '', False, None)]

            if classes:
                classes.sort(key=lambda doccls: doccls.priority)
                # print name, classes
                doccls = classes[-1]
            else:
                doccls = DataDocumenter

            if doccls.objtype == autodoc_member_type:

                if member_type == "data":
                    prefix = "`" + type(member).__name__ + "`" if add_prefix else ""
                    relative_member_name = name
                    absolute_member_name = ".".join([self.current_module_name, relative_member_name])
                if member_type == "function":
                    prefix = "`def`" if add_prefix else ""
                    relative_member_name = name
                    absolute_member_name = ".".join([self.current_module_name, relative_member_name])
                if member_type == "attribute":
                    prefix = "`" + type(member).__name__ + "`" if add_prefix else ""
                    relative_member_name = ".".join([self.current_class_name, name])
                    absolute_member_name = ".".join([self.current_module_name, relative_member_name])
                if member_type == "class":
                    prefix = "`" + type(member).__name__ + "`" if add_prefix else ""
                    relative_member_name = ".".join([self.current_class_name, name])
                    absolute_member_name = ".".join([self.current_module_name, relative_member_name])
                if member_type == "method":
                    prefix = "`def`" if add_prefix else ""
                    relative_member_name = ".".join([self.current_class_name, name])
                    absolute_member_name = ".".join([self.current_module_name, relative_member_name])

                items.append((prefix, relative_member_name, absolute_member_name, member_type))

        return items

    def filter_names(self, names):
        """Filters names generated by :meth:`get_items` based on the options ``members``, ``private-members`` and ``special-members``.
        If ``private-members`` is given without text (ie. all), ``special-members`` is ignored since all special members are also private
        """
        include_members = self.get_arg_option('members')
        include_all_members = include_members is True
        if include_members is not False and not include_all_members:
            user_members = filter(lambda member: not member.startswith("_"),
                                  [member.strip() for member in include_members.split(",")])

        include_private = self.get_arg_option('private-members')
        include_all_private = include_private is True
        if include_private is not False and not include_all_private:
            user_private = filter(lambda member: member.startswith("_") and len(member) > 1,
                                  [member.strip() for member in include_private.split(",")])

        include_special = self.get_arg_option('special-members')
        include_all_special = include_special is True
        if include_special is not False and not include_all_special:
            user_special = filter(lambda member: member.startswith("__") and member.endswith("__") and len(member) > 4,
                                  [member.strip() for member in include_special.split(",")])

        exclude_members = self.get_arg_option('exclude-members')
        exclude_all_members = exclude_members is True
        if exclude_members is not False and not exclude_all_members:
            user_exclude = [member.strip() for member in exclude_members.split(",")]

        def key(name):
            if exclude_members:
                if exclude_all_members:
                    return False
                elif name in user_exclude:
                    return False

            is_private = name.startswith('_') and len(name) > 1
            is_special = name.startswith("__") and name.endswith("__") and len(name) > 4
            is_member = not is_private

            if is_member and include_members:
                return include_all_members or name in user_members
            elif is_private and include_private:
                return (include_all_private or name in user_private
                        or (include_all_special or name in user_special if is_special and include_special else False))
            elif is_special and include_special:
                return include_all_special or name in user_special
            elif is_private or is_special:
                return False

            return True

        return filter(key, names)

    def order_items(self, items):
        """Orders items for the table based on the ``member-order`` option or corresponding config value within ``autobasicsummary_default_options``."""
        member_type_order = self.env.config.autobasicsummary_member_type_order
        member_order = self.get_options().get('member-order')

        if member_order == "groupwise":
            def key(item):
                # Sort by member_type order first then by relative member name
                return (member_type_order[item[3]], item[1])

            items.sort(key=key)

        elif member_order == "bysource":
            try:
                analyzer = ModuleAnalyzer.for_module(self.current_module_name)
                analyzer.find_attr_docs()
            except PycodeError:
                analyzer = None

            if analyzer:
                tagorder = analyzer.tagorder

                def key(item):
                    return analyzer.tagorder.get(item[1], len(tagorder))

                items.sort(key=key)

        elif member_order == "alphabetical":
            def key(item):
                # Sort by relative member name
                return item[1]

            items.sort(key=key)

        else:
            raise ValueError("{} : member-order not recognised, must be one of : {}".format(member_order, self._member_orders))

    def get_table(self, items, title=None):
        """Generates a list of table nodes for the ``autobasicsummary::`` directive.
        ``items`` is a list of three element tuples containing a prefix, relative and absolute member name and member type for each member produced by :meth:`get_items`.
        ``title`` is an optional argument which will append a thead node to the table.
        """
        line = 0

        def append_data_row(column_text, member_type, body):
            # Create tr
            row = nodes.row('')
            # Create td
            entry = nodes.entry('')
            # Create para
            para = nodes.paragraph('', classes=['autobasicsummary-{}-data'.format(member_type)])
            # Parse rst as para contents
            rst = ViewList()
            rst.append(column_text, "fakefile.rst", line)
            self.state.nested_parse(rst, 0, para)
            # Append para as td child
            entry.append(para)
            # Append td as tr child
            row.append(entry)
            # Append tr as tbody child
            body.append(row)

        def append_header_row(title, head):
            # Create tr
            row = nodes.row('')
            # Create th
            entry = nodes.entry('', classes=['autobasicsummary-header'])
            # Parse rst as th contents
            rst = ViewList()
            rst.append(title, "fakefile.rst", line)
            self.state.nested_parse(rst, 0, entry)
            # Append th as tr child
            row.append(entry)
            # Append tr as thead child
            head.append(row)

        table_spec = addnodes.tabular_col_spec()
        table_spec['spec'] = r'\X{1}{2}'

        table = autobasicsummary('')
        # Create table
        real_table = nodes.table('', classes=['longtable'])
        table.append(real_table)
        # Create tgroup and append as table child (creates a colgroup)
        group = nodes.tgroup('', cols=1)
        real_table.append(group)
        # Create col and append to tgroup (parents to colgroup)
        col = nodes.colspec('', colwidth=100)
        group.append(col)

        if title:
            # Create thead and append to tgroup (parents to table)
            head = nodes.thead('')
            group.append(head)
            append_header_row(title, head)
            line += 1

        # Create tbody and append to tgroup (parents to table)
        body = nodes.tbody('')
        group.append(body)

        for (prefix, relative_member_name, absolute_member_name, member_type) in items:
            role = self._member_type_role_mapping[member_type]
            prefix_sep = " " if prefix else ""
            column_text = prefix + prefix_sep + ':%s:`~%s`' % (role, absolute_member_name)
            append_data_row(column_text, member_type, body)
            line += 1

        return [table_spec, table]
