from clang import cindex
import sys
import yaml
import re
import os
import inspect
import traceback
from Cheetah.Template import Template

from configparser import ConfigParser

generator = None

luaTypeInfo = {
    'bool': 'boolean',
    'std::string': 'string',
    'std::string_view': 'string',
    'std::vector<std::string>': 'string[]',
    'std::vector<std::string_view>': 'string[]',
}

sortedKeys = []
def getSortedLuaTransKeys():
    if not sortedKeys:
        keys = generator.config['conversions']['ns_map'].keys()
        for k in keys:
            sortedKeys.append(k)
        sortedKeys.sort(reverse=True, key=lambda v: len(v))
        print('sortedKeys', sortedKeys)
    return sortedKeys

def transTypeNameToLua(nameSpaceTypeName):
    ret = nameSpaceTypeName
    for k in getSortedLuaTransKeys():
        if nameSpaceTypeName.startswith(k):
            v = generator.config['conversions']['ns_map'][k]
            ret = ret.replace(k, v).replace('::', '.')
            break

    ret = luaTypeInfo.get(ret, ret).replace('*', '')
    if ret.startswith('ax.Vector<'):
        ret = ret[10:-2] + '[]'

    if ret.find('::') != -1 or ret.find('<') != -1:
        print('not parsed type:', ret, nameSpaceTypeName)
    return ret

type_map = {
    cindex.TypeKind.VOID        : "void",
    cindex.TypeKind.BOOL        : "bool",
    cindex.TypeKind.CHAR_U      : "unsigned char",
    cindex.TypeKind.UCHAR       : "unsigned char",
    cindex.TypeKind.CHAR16      : "char",
    cindex.TypeKind.CHAR32      : "char",
    cindex.TypeKind.USHORT      : "unsigned short",
    cindex.TypeKind.UINT        : "unsigned int",
    cindex.TypeKind.ULONG       : "unsigned long",
    cindex.TypeKind.ULONGLONG   : "unsigned long long",
    cindex.TypeKind.CHAR_S      : "char",
    cindex.TypeKind.SCHAR       : "char",
    cindex.TypeKind.WCHAR       : "wchar_t",
    cindex.TypeKind.SHORT       : "short",
    cindex.TypeKind.INT         : "int",
    cindex.TypeKind.LONG        : "long",
    cindex.TypeKind.LONGLONG    : "long long",
    cindex.TypeKind.FLOAT       : "float",
    cindex.TypeKind.DOUBLE      : "double",
    cindex.TypeKind.LONGDOUBLE  : "long double",
    cindex.TypeKind.NULLPTR     : "NULL",
    cindex.TypeKind.OBJCID      : "id",
    cindex.TypeKind.OBJCCLASS   : "class",
    cindex.TypeKind.OBJCSEL     : "SEL",
    # cindex.TypeKind.ENUM        : "int"
}

INVALID_NATIVE_TYPE = "??"

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

stl_type_map = {
    'std_function_args': 1000,
    'std::unordered_map': 2,
    'std::unordered_multimap': 2,
    'std::map': 2,
    'tsl::robin_map': 2,
    'hlookup::string_map': 2,
    'std::multimap': 2,
    'std::vector': 1,
    'std::list': 1,
    'std::forward_list': 1,
    'std::priority_queue': 1,
    'std::set': 1,
    'std::multiset': 1,
    'std::unordered_set': 1,
    'std::unordered_multiset': 1,
    'tsl::robin_set': 1,
    'hlookup::string_set': 1,
    'std::stack': 1,
    'std::queue': 1,
    'std::deque': 1,
    'std::array': 1,

    'unordered_map': 2,
    'unordered_multimap': 2,
    'map': 2,
    'multimap': 2,
    'robin_map': 2,
    'string_map': 2,
    'vector': 1,
    'list': 1,
    'forward_list': 1,
    'priority_queue': 1,
    'set': 1,
    'multiset': 1,
    'unordered_set': 1,
    'unordered_multiset': 1,
    'robin_set': 1,
    'string_set': 1,
    'stack': 1,
    'queue': 1,
    'deque': 1,
    'array': 1
}

def find_sub_string_count(s, start, end, substr):
    count = 0
    pos = s.find(substr, start, end)
    if pos != -1:
        next_count = find_sub_string_count(s, pos + 1, end, substr)
        count = next_count + 1
    return count

def split_container_name(name):
    name = name.strip()
    left = name.find('<')
    right = -1

    if left != -1:
        right = name.rfind('>')

    if left == -1 or right == -1:
        return [name]

    first = name[:left]
    results = [first]

    comma = name.find(',', left + 1, right)
    if comma == -1:
        results.append(name[left+1:right].strip())
        return results


    left += 1
    while comma != -1:
        lt_count = find_sub_string_count(name, left, comma, '<')
        gt_count = find_sub_string_count(name, left, comma, '>')
        if lt_count == gt_count:
            results.append(name[left:comma].strip())
            left = comma + 1
        comma = name.find(',', comma + 1, right)

    if left < right:
        results.append(name[left:right].strip())
    name_len = len(name)
    if right < name_len - 1:
        results.append(name[right+1:].strip())

    return results


def normalize_type_name_by_sections(sections):
    container_name = sections[0]
    suffix = ''

    index = len(sections) - 1
    while sections[index] == '*' or sections[index] == '&':
        suffix += sections[index]
        index -= 1

    name_for_search = container_name.replace('const ', '').replace('&', '').replace('*', '').strip()
    if name_for_search in stl_type_map:
        normalized_name = container_name + '<' + ', '.join(sections[1:1+stl_type_map[name_for_search]]) + '>' + suffix
    else:
        normalized_name = container_name + '<' + ', '.join(sections[1:]) + '>'

    return normalized_name


def normalize_std_function_by_sections(sections):
    normalized_name = ''
    if sections[0] == 'std_function_args':
        normalized_name = '(' + ', '.join(sections[1:]) + ')'
    elif sections[0] == 'std::function' or sections[0] == 'function':
        normalized_name = 'std::function<' + sections[1] + ' ' + sections[2] + '>'
    else:
        assert(False)
    return normalized_name


def normalize_type_str(s, depth=1):
    if s.find('std::function') == 0 or s.find('function') == 0:
        start = s.find('<')
        assert(start > 0)
        sections = [s[:start]] # std::function
        start += 1
        ret_pos = s.find('(', start)
        sections.append(s[start:ret_pos].strip()) # return type
        end = s.find(')', ret_pos + 1)
        sections.append('std_function_args<' + s[ret_pos+1:end].strip() + '>')
    else:
        sections = split_container_name(s)
    section_len = len(sections)
    if section_len == 1:
        return sections[0]

    # for section in sections:
    #     print('>' * depth + section)

    if sections[0] == 'const std::basic_string' or sections[0] == 'const basic_string':
        last_section = sections[len(sections) - 1]
        if last_section == '&' or last_section == '*' or last_section.startswith('::'):
            return 'const std::string' + last_section
        else:
            return 'const std::string'

    elif sections[0] == 'std::basic_string' or sections[0] == 'basic_string':
        last_section = sections[len(sections) - 1]
        if last_section == '&' or last_section == '*' or last_section.startswith('::'):
            return 'std::string' + last_section
        else:
            return 'std::string'

    # for std::string_view
    if sections[0] == 'const std::basic_string_view' or sections[0] == 'const basic_string_view':
        last_section = sections[len(sections) - 1]
        if last_section == '&' or last_section == '*' or last_section.startswith('::'):
            return 'const std::string_view' + last_section
        else:
            return 'const std::string_view'

    elif sections[0] == 'std::basic_string_view' or sections[0] == 'basic_string_view':
        last_section = sections[len(sections) - 1]
        if last_section == '&' or last_section == '*' or last_section.startswith('::'):
            return 'std::string_view' + last_section
        else:
            return 'std::string_view'        
           
    # for compatible cxx17::string_view
    if sections[0] == 'const cxx17::basic_string_view' or sections[0] == 'const basic_string_view':
        last_section = sections[len(sections) - 1]
        if last_section == '&' or last_section == '*' or last_section.startswith('::'):
            return 'const cxx17::string_view' + last_section
        else:
            return 'const cxx17::string_view'

    elif sections[0] == 'cxx17::basic_string_view' or sections[0] == 'basic_string_view':
        last_section = sections[len(sections) - 1]
        if last_section == '&' or last_section == '*' or last_section.startswith('::'):
            return 'cxx17::string_view' + last_section
        else:
            return 'cxx17::string_view'

    if sections[0] == 'const std::__thread_id' or sections[0] == 'const __thread_id':
        last_section = sections[len(sections) - 1]
        if last_section == '&' or last_section == '*' or last_section.startswith('::'):
            return 'const std::thread::id' + last_section
        else:
            return 'const std::thread::id'

    elif sections[0] == 'std::__thread_id' or sections[0] == '__thread_id':
        last_section = sections[len(sections) - 1]
        if last_section == '&' or last_section == '*' or last_section.startswith('::'):
            return 'std::thread::id' + last_section
        else:
            return 'std::thread::id'       

    for i in range(1, section_len):
        sections[i] = normalize_type_str(sections[i], depth+1)

    if sections[0] == 'std::function' or sections[0] == 'function' or sections[0] == 'std_function_args':
        normalized_name = normalize_std_function_by_sections(sections)
    else:
        normalized_name = normalize_type_name_by_sections(sections)
    return normalized_name


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

def native_name_from_type(ntype, underlying=False):
    kind = ntype.kind
    if not underlying and kind == cindex.TypeKind.ENUM:
        decl = ntype.get_declaration()
        return get_namespaced_name(decl)
    elif kind in type_map:
        return type_map[kind]
    elif kind == cindex.TypeKind.RECORD:
        # might be an std::string
        decl = ntype.get_declaration()
        parent = decl.semantic_parent
        cdecl = ntype.get_canonical().get_declaration()
        cparent = cdecl.semantic_parent
        if decl.spelling == "string" and parent and parent.spelling == "std":
            return "std::string"
        elif cdecl.spelling == "function" and cparent and cparent.spelling == "std":
            return "std::function"
        elif decl.spelling == "string_view" and parent and parent.spelling == "cxx17":
            return "cxx17::string_view"
        else:
            print("error Unknown type 111" + str(decl.spelling))
            return INVALID_NATIVE_TYPE
    else:
        print("error Unknown type 222" + str(ntype.get_declaration().spelling))
        return INVALID_NATIVE_TYPE

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