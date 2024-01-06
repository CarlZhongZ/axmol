from clang import cindex
import sys
import yaml
import re
import os
import inspect
import traceback
import json
from Cheetah.Template import Template

with open('configs/parse_config.json', 'r') as f:
    parseConfig = json.loads(f.read())

parsedEnums = {}

parsedStructs = {}

parsedClasses = {}

# 只会导出 ns_map 记录的命名空间中的类
ns_map = parseConfig['ns_map']

def getLuaGlobalVarNames():
    ret = []
    for _, v in ns_map:
        vv = v[:-1]
        if vv not in ret:
            ret.append(vv)

    return ret

def nsNameToLuaName(namespace_name):
    for ns, luaName in ns_map:
        if namespace_name.startswith(ns):
            return luaName[0:-1]

    return None

def isTargetedNamespace(cursor):
    if len(cursor.displayname) == 0:
        return False

    return nsNameToLuaName(get_namespace_name(cursor)) is not None

def transTypeNameToLua(nameSpaceTypeName):
    for k, v in ns_map:
        if nameSpaceTypeName.startswith(k):
            return nameSpaceTypeName.replace(k, v).replace("::", ".")
    return nameSpaceTypeName.replace("::", ".")

default_arg_type_arr = [

# An integer literal.
cindex.CursorKind.INTEGER_LITERAL,

# A floating point number literal.
cindex.CursorKind.FLOATING_LITERAL,

# An imaginary number literal.
cindex.CursorKind.IMAGINARY_LITERAL,

# A string literal.
cindex.CursorKind.STRING_LITERAL,

# A character literal.
cindex.CursorKind.CHARACTER_LITERAL,

# [C++ 2.13.5] C++ Boolean Literal.
cindex.CursorKind.CXX_BOOL_LITERAL_EXPR,

# [C++0x 2.14.7] C++ Pointer Literal.
cindex.CursorKind.CXX_NULL_PTR_LITERAL_EXPR,

cindex.CursorKind.GNU_NULL_EXPR,

# An expression that refers to some value declaration, such as a function,
# varible, or enumerator.
cindex.CursorKind.DECL_REF_EXPR
]

class BaseEnumeration(object):
    """
    Common base class for named enumerations held in sync with Index.h values.

    Subclasses must define their own _kinds and _name_map members, as:
    _kinds = []
    _name_map = None
    These values hold the per-subclass instances and value-to-name mappings,
    respectively.

    """

    def __init__(self, value):
        if value >= len(self.__class__._kinds):
            self.__class__._kinds += [None] * (value - len(self.__class__._kinds) + 1)
        if self.__class__._kinds[value] is not None:
            raise ValueError('{0} value {1} already loaded'.format(
                str(self.__class__), value))
        self.value = value
        self.__class__._kinds[value] = self
        self.__class__._name_map = None


    def from_param(self):
        return self.value

    @property
    def name(self):
        """Get the enumeration name of this cursor kind."""
        if self._name_map is None:
            self._name_map = {}
            for key, value in self.__class__.__dict__.items():
                if isinstance(value, self.__class__):
                    self._name_map[value] = key
        return self._name_map[self]

    @classmethod
    def from_id(cls, id):
        if id >= len(cls._kinds) or cls._kinds[id] is None:
            raise ValueError('Unknown template argument kind %d' % id)
        return cls._kinds[id]

    def __repr__(self):
        return '%s.%s' % (self.__class__, self.name,)

### Availability Kinds ###

class AvailabilityKind(BaseEnumeration):
    """
    Describes the availability of an entity.
    """

    # The unique kind objects, indexed by id.
    _kinds = []
    _name_map = None

    def __repr__(self):
        return 'AvailabilityKind.%s' % (self.name,)

AvailabilityKind.AVAILABLE = AvailabilityKind(0)
AvailabilityKind.DEPRECATED = AvailabilityKind(1)
AvailabilityKind.NOT_AVAILABLE = AvailabilityKind(2)
AvailabilityKind.NOT_ACCESSIBLE = AvailabilityKind(3)

def get_availability(cursor):
    """
    Retrieves the availability of the entity pointed at by the cursor.
    """
    if not hasattr(cursor, '_availability'):
        cursor._availability = cindex.conf.lib.clang_getCursorAvailability(cursor)

    return AvailabilityKind.from_id(cursor._availability)

def build_namespace(cursor, namespaces=[]):
    '''
    build the full namespace for a specific cursor
    '''
    if cursor:
        parent = cursor.semantic_parent
        if parent:
            if parent.kind == cindex.CursorKind.NAMESPACE or parent.kind == cindex.CursorKind.CLASS_DECL:
                namespaces.append(parent.displayname)
                build_namespace(parent, namespaces)

    return namespaces

def get_namespaced_name(declaration_cursor):
    ns_list = build_namespace(declaration_cursor, [])
    ns_list.reverse()
    ns = "::".join(ns_list)
    display_name = declaration_cursor.displayname.replace("::__ndk1", "")
    if len(ns) > 0:
        ns = ns.replace("::__ndk1", "")
        return ns + "::" + display_name
    return display_name

def generate_namespace_list(cursor, namespaces=[]):
    '''
    build the full namespace for a specific cursor
    '''
    if cursor:
        parent = cursor.semantic_parent
        if parent:
            if parent.kind == cindex.CursorKind.NAMESPACE or parent.kind == cindex.CursorKind.CLASS_DECL:
                if parent.kind == cindex.CursorKind.NAMESPACE:
                    namespaces.append(parent.displayname)
                generate_namespace_list(parent, namespaces)
    return namespaces

def get_namespace_name(declaration_cursor):
    ns_list = generate_namespace_list(declaration_cursor, [])
    ns_list.reverse()
    ns = "::".join(ns_list)

    if len(ns) > 0:
        ns = ns.replace("::__ndk1", "")
        return ns + "::"

    return declaration_cursor.displayname

# return True if found default argument.
def iterate_param_node(param_node, depth=1):
    for node in param_node.get_children():
        # print(">"*depth+" "+str(node.kind))
        if node.kind in default_arg_type_arr:
            return True

        if iterate_param_node(node, depth + 1):
            return True

    return False

def isValidDefinition(cursor):
    if cursor != cursor.type.get_declaration():
        return False
    
    if not isTargetedNamespace(cursor):
        return False

    iter = cursor.get_children()
    for _ in iter:
        return True
    return False
