from clang import cindex
import re
import os
import json
from Cheetah.Template import Template
from NativeType import NativeType
from NativeClass import NativeClass
from NativeStruct import NativeStruct
from NativeEnum import NativeEnum


with open('configs/parse_config.json', 'r') as f:
    parseConfig = json.loads(f.read())

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

default_arg_type_arr = set([
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
])

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

def isValidMethod(cursor):
    # skip if variadic
    return get_availability(cursor) != AvailabilityKind.DEPRECATED and not cursor.type.is_function_variadic()

def isValidConstructor(cursor):
    return not cursor.is_copy_constructor() and not cursor.is_move_constructor()

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

notUsedClassMemberCursorKind = set([
    cindex.CursorKind.DESTRUCTOR, 
    cindex.CursorKind.FRIEND_DECL, 
    cindex.CursorKind.TYPEDEF_DECL, 
    cindex.CursorKind.FUNCTION_TEMPLATE, 
    cindex.CursorKind.USING_DECLARATION, 
    cindex.CursorKind.TYPE_ALIAS_DECL
    ])
# def parseClass(cursor):

classOrStructMemberCursorKind = set([
    cindex.CursorKind.FIELD_DECL, 
    cindex.CursorKind.CXX_METHOD, 
    cindex.CursorKind.CONSTRUCTOR, 
])

# test print cursor
def parseCuorsor(cursor):
    print('parsing cursor', get_namespaced_name(cursor))

    def _parse(node, level):
        tp = NativeType.from_type(node.type)
        print(level, node.kind, node.spelling, node.displayname, tp.ns_full_name)
        for node in node.get_children():
            _parse(node, level + 1)

    _parse(cursor, 0)

    print('parsing cursor end')




clang_args = None

engine_path = os.path.abspath('../..')

parsedEnums = {}

parsedStructs = {}

parsedClasses = {}

classes = {}

# 内存由 c++ 管理， 需要在析构的时候做销毁处理
ref_classes = set()
for ns, names in parseConfig['ref_classes'].items():
    for name in names:
        ref_classes.add(f'{ns}{name}')

# 内存由 lua 管理， lua gc 的时候会将该对象内存销毁
non_ref_classes = set()
for ns, names in parseConfig['non_ref_classes'].items():
    for name in names:
        non_ref_classes.add(f'{ns}{name}')

# 将类对待成 struct
struct_classes = set(parseConfig['struct_classes'])

costomize_struct = parseConfig['costomize_struct']

# 该类会在lua中被扩展，标记一个新的扩展类名供生成 lua 静态类型用
custom_lua_class_info = set()
for ns, names in parseConfig['custom_lua_class_info'].items():
    for name in names:
        custom_lua_class_info.add(f'{ns}{name}')

# c++ 的类对应的 String lua 类型
string_types = parseConfig['string_types']

# c++ 的类对应的 array lua 类型
array_types = parseConfig['array_types']

def tryParseArrayType(nsName):
    for tp, addMethodName in array_types.items():
        eleType = None
        addMethod = None
        if nsName.startswith(tp):
            idx = nsName.find('<')
            if idx != -1:
                eleType = NativeType.from_type_str(nsName[idx + 1:-1])
                addMethod = addMethodName

        if eleType:
            return True, eleType, addMethod

    return False, None, None

def tryParseTableType(nsName):
    return False, None, None

skip_members = parseConfig['skip_members']
def isMethodShouldSkip(nsName, methodName):
    skipMethods = skip_members.get(nsName)
    if not skipMethods:
        return False

    if methodName in skipMethods:
        return True
    for reName in skipMethods:
        if re.match(reName, methodName):
            return True

    return False

def _isValidStructClassName(nsName):
    return nsName in struct_classes

def _isValidClassName(nsName):
    if nsName in non_ref_classes or nsName in ref_classes:
        return True

    for ns, names in classes.items():
        if not nsName.startswith(ns):
            continue
        className = nsName.replace(ns, '')
        for name in names:
            md = re.match("^" + name + "$", className)
            if md:
                return True

    return False

def _isValidDefinition(cursor):
    if cursor != cursor.type.get_declaration():
        return False
    
    if not isTargetedNamespace(cursor):
        return False

    iter = cursor.get_children()
    for _ in iter:
        return True
    return False

def tryParseTypes(cursor):
    if not _isValidDefinition(cursor):
        return

    nsName = get_namespaced_name(cursor)
    if cursor.kind == cindex.CursorKind.CLASS_DECL:
        if _isValidClassName(nsName) and nsName not in parsedClasses:
            parsedClasses[nsName] = NativeClass(cursor)
        elif _isValidStructClassName(nsName) and nsName not in parsedStructs:
            parsedStructs[nsName] = NativeStruct(cursor)
        return True
    elif cursor.kind == cindex.CursorKind.STRUCT_DECL:
        if nsName not in parsedStructs:
            parsedStructs[nsName] = NativeStruct(cursor)
        return True
    elif cursor.kind == cindex.CursorKind.ENUM_DECL:
        if nsName not in parsedEnums:
            parsedEnums[nsName] = NativeEnum(cursor)
        return True

def tryParseParent(cursor):
    if cursor.kind == cindex.CursorKind.CXX_BASE_SPECIFIER:
        parent = cursor.get_definition()

        if parent.displayname:
            parentNSName = get_namespaced_name(parent)
            if parentNSName not in parsedClasses:
                parsedClasses[parentNSName] = NativeClass(parent)

            return parsedClasses[parentNSName]

def _pretty_print(diagnostics):
    errors=[]
    for idx, d in enumerate(diagnostics):
        if d.severity > 2:
            errors.append(d)
    if len(errors) == 0:
        return
    print("====\nErrors in parsing headers:")
    severities=['Ignored', 'Note', 'Warning', 'Error', 'Fatal']
    for idx, d in enumerate(errors):
        print("%s. <severity = %s,\n    location = %r,\n    details = %r>" % (
            idx+1, severities[d.severity], d.location, d.spelling))
    print("====\n")

def _parseHeaders():
    index = cindex.Index.create()
    for header in parseConfig['parse_engine_headers']:
        print("parsing header => %s" % header)
        tu = index.parse(os.path.join(engine_path, header), clang_args)
        if len(tu.diagnostics) > 0:
            _pretty_print(tu.diagnostics)
            is_fatal = False
            for d in tu.diagnostics:
                if d.severity >= cindex.Diagnostic.Error:
                    is_fatal = True
            if is_fatal:
                print("*** Found errors - can not continue")
                raise Exception("Fatal error in parsing headers")

        def _parse(cursor):
            if not tryParseTypes(cursor):
                for node in cursor.get_children():
                    _parse(node)
        _parse(tu.cursor)

def _sorted_parents(nclass):
    sorted_parents = []
    for p in nclass.parents:
        sorted_parents += _sorted_parents(p)
    sorted_parents.append(nclass.ns_full_name)
    return sorted_parents

def _getSortedClasses():
    sorted_list = []
    for nsName in sorted(parsedClasses.keys()):
        nclass = parsedClasses[nsName]
        sorted_list += _sorted_parents(nclass)
    # remove dupes from the list
    no_dupes = []
    [no_dupes.append(i) for i in sorted_list if not no_dupes.count(i)]
    return no_dupes

def generateCode():
    _parseHeaders()

    outdir = os.path.abspath(os.path.join(engine_path, 'extensions/scripting/lua-bindings/auto'))

    useTypes = set()
    realUseTypes = set()
    for _, nativeClass in parsedClasses.items():
        nativeClass.testUseTypes(useTypes)
        realUseTypes.add(nativeClass.ns_full_name)

    enumTypes = []
    structTypes = []
    for tp in useTypes:
        if tp in parsedEnums:
            enumTypes.append(tp)
            realUseTypes.add(tp)
        elif tp in parsedStructs:
            structTypes.append(tp)
            realUseTypes.add(tp)

    NativeType.onParseCodeEnd(realUseTypes)

    validStructs = []
    for tp in structTypes:
        if parsedStructs[tp].isNotSupported:
            continue
        validStructs.append(tp)

    enumTypes.sort()
    validStructs.sort()
    structTypes = validStructs

    classTypes = _getSortedClasses()

    f = open(os.path.abspath("../../app/Content/src/framework/declare_types/auto/engine_types.lua"), "wt+", encoding='utf8', newline='\n')
    regAllClassesOrStructs = {}
    arrRegAllClassesOrStructs = []
    for tp in structTypes:
        regAllClassesOrStructs[tp] = parsedStructs[tp]
        arrRegAllClassesOrStructs.append(parsedStructs[tp])
    for tp in classTypes:
        regAllClassesOrStructs[tp] = parsedClasses[tp]
        arrRegAllClassesOrStructs.append(parsedClasses[tp])

    # 嵌套类型索引信息定义
    declareSubTypeInfo = {}
    for nsName in enumTypes:
        enumInfo = parsedEnums[nsName]
        parentDeclare = enumInfo.parentDeclare
        if parentDeclare in regAllClassesOrStructs:
            if parentDeclare not in declareSubTypeInfo:
                declareSubTypeInfo[parentDeclare] = []
            declareSubTypeInfo[parentDeclare].append(f'---@field {enumInfo.class_name} {enumInfo.luaClassName}Enum')

    for nsName in structTypes:
        info = parsedStructs[nsName]
        parentDeclare = info.parentDeclare
        if parentDeclare in regAllClassesOrStructs:
            if parentDeclare not in declareSubTypeInfo:
                declareSubTypeInfo[parentDeclare] = []
            declareSubTypeInfo[parentDeclare].append(f'---@field {info.class_name} {info.luaClassName}S')

    f.write(str(Template(file='configs/engine_types.lua.tmpl',
                                searchList=[{
                                    'declareSubTypeInfo': declareSubTypeInfo,
                                    'arrRegAllClassesOrStructs': arrRegAllClassesOrStructs,
                                    'luaGlobalVars': getLuaGlobalVarNames(),
                                    'enumTypes': enumTypes,
                                    'parsedEnums' :parsedEnums,
                                }])))

    fEnum = open(os.path.abspath("../../app/Content/src/framework/declare_types/auto/engine_enums.lua"), "wt+", encoding='utf8', newline='\n')
    fEnum.write(str(Template(file='configs/engine_enums.lua.tmpl',
                                searchList=[{
                                    'enumTypes': enumTypes,
                                    'parsedEnums' :parsedEnums,
                                }])))



    fAutoConvertCodes = open(os.path.join(outdir, "tolua_auto_convert.h"), "wt+", encoding='utf8', newline='\n')
    fAutoConvertCodes.write(str(Template(file='configs/tolua_auto_convert.h.tmpl',
                                searchList=[{
                                    'code_includes': parseConfig['code_includes'],
                                    'structTypes': structTypes,
                                    'parsedStructs': parsedStructs,
                                }])))
    
    fAutoConvertCodes = open(os.path.join(outdir, "tolua_auto_convert.cpp"), "wt+", encoding='utf8', newline='\n')
    fAutoConvertCodes.write(str(Template(file='configs/tolua_auto_convert.cpp.tmpl',
                                searchList=[{
                                    'structTypes': structTypes,
                                    'parsedStructs': parsedStructs,
                                }])))

    # gen cpp audo code
    fAutoGenCodesCpp = open(os.path.join(outdir, "lua_auto_gen_codes.cpp"), "wt+", encoding='utf8', newline='\n')
    fAutoGenCodesCpp.write(str(Template(file='configs/lua_auto_gen_codes.cpp.tmpl',
                                searchList=[{
                                    'code_includes': parseConfig['code_includes'],
                                    'arrRegAllClassesOrStructs': arrRegAllClassesOrStructs,
                                    'classTypes': classTypes,
                                    'parsedClasses': parsedClasses,
                                }])))
    


    # write test classes info
    fClassInfo = open(os.path.join("configs/classes.txt"), "wt+", encoding='utf8', newline='\n')
    for _, cls in parsedClasses.items():
        base = cls.parents[0].ns_full_name if cls.parents else 'None'
        fClassInfo.write(f'\n\n\nclass:{cls.ns_full_name} base:{base} isRefClass:{cls.isRefClass}\n')
        for m in cls.methods:
            fClassInfo.write(f'\t{m.cursor.displayname} {m.isNotSupported}\n')
            fClassInfo.write('\t')
            for t in m.arguments:
                fClassInfo.write(f'\t{t.ns_full_name}: {t.isNotSupported} {t.not_supported} {t.is_pointer} {t.is_reference} {t.is_class} {t.is_string}')
            fClassInfo.write('\n')



def isMethodInParents(current_class, method_name):
    if len(current_class.parents) > 0:
        for m in current_class.parents[0].methods:
            if method_name == m.name:
                return True
        return isMethodInParents(current_class.parents[0], method_name)

    return False
