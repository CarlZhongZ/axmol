from clang import cindex
import sys
import yaml
import re
import os
import inspect
import traceback
from Cheetah.Template import Template

import ConvertUtils

allTypes = {}
allCreatedTypes = []

numberTypes = {
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
}

_numberTypeset = set()
for (_, v) in numberTypes.items():
    _numberTypeset.add(v)

_stringTypes = set([
    'std::basic_string_view<char>',
    'std::basic_string<char>',
])

def regStringType(typeName):
    _stringTypes.add(typeName)

_arrayParseFun = []
def regArrayType(parseFun):
    _arrayParseFun.append(parseFun)

_tableParseFun = []
def regTableType(parseFun):
    _tableParseFun.append(parseFun)

def genFunctionParms(parmsStrs, cur=None):
    ret = []
    size = len(parmsStrs)
    if size == 0:
        return ret

    if cur is None:
        cur = 0

    c1 = '<'
    c2 = '>'
    c1Count = 0
    parmSep = ', '

    while cur < size:
        if c1Count == 0:
            pos = parmsStrs.find(parmSep, cur)
            if pos == -1:
                ret.append(parmsStrs[cur:])
                return ret

            pos1 = parmsStrs.find(c1, cur)
            if pos1 == -1 or pos < pos1:
                ret.append(parmsStrs[cur:pos])
                cur = pos + 2
            else:
                cur = pos1 + 1
                ++c1Count
        else:
            pos1 = parmsStrs.find(c1, cur)
            pos2 = parmsStrs.find(c2, cur)
            assert(pos2 != -1)
            if pos1 != -1 and pos1 < pos2:
                ++c1Count
                cur = pos1 + 1
            else:
                --c1Count
                cur = pos2 + 1

    print('warning function params not valid:%s' % parmsStrs)

def _tryParseFunction(nsName, name):
    if not nsName.startswith('std::function<'):
        return (False, None, None)

    funDef = nsName[14:-1]
    if funDef.find('function') != -1:
        # 不支持函数嵌套
        return (False, None, None)

    i = funDef.find(' (')
    ret_type = NativeType.from_type_str(funDef[:i])

    param_types = []
    paramsStrs = genFunctionParms(funDef[i+2:-1])
    for param in paramsStrs:
        param_types.append(NativeType.from_type_str(param))

    return (True, ret_type, param_types)


class NativeType(object):
    def __init__(self):
        allCreatedTypes.append(self)

        self.not_supported = False

        self.is_class = False
        self.is_native_gc_obj = True

        self.is_void = False
        self.is_boolean = False
        self.is_enum = False
        self.is_numeric = False
        self.is_string = False

        self.is_table = False
        self.table_ele_type = None

        self.is_array = False
        self.array_ele_type = None

        self.is_function = False
        self.param_types = None
        self.ret_type = None

        self.namespaced_name = '' # with namespace and class name
        self.name = ''
        self.whole_name = ''
        self.lua_name = ''

        self.is_const = False
        self.is_pointer = False
        self.is_reference = False

    def _onParseCodeEndCheck(self, useTypes):
        namespaced_name = self.namespaced_name
        if self.is_enum:
            assert(namespaced_name in ConvertUtils.parsedEnums, namespaced_name)
        elif self.is_class:
            if namespaced_name in ConvertUtils.parsedEnums:
                # 由字符串创建的 type 不能判定是否为 枚举类型
                self.is_class = False
                self.is_enum = True

        if self.is_enum or self.is_class:
            # print('sssss not_supported', self.namespaced_name)
            if self.namespaced_name not in useTypes:
                self.not_supported = True
            elif self.namespaced_name in ConvertUtils.parsedStructs and ConvertUtils.parsedStructs[self.namespaced_name].isNotSupported:
                self.not_supported = True


    @staticmethod
    def onParseCodeEnd(useTypes):
        for tp in allCreatedTypes:
            tp._onParseCodeEndCheck(useTypes)

    def _initWithType(self, ntype):
        decl = ntype.get_declaration()

        cntype = ntype.get_canonical()
        cdecl = cntype.get_declaration()

        declDisplayName = decl.displayname
        cdeclDisplayName = cdecl.displayname # 去掉 typedef 的原型
        if len(cdeclDisplayName) > 0 and cdeclDisplayName != declDisplayName:
            displayname = cdeclDisplayName
            self.namespaced_name = ConvertUtils.get_namespaced_name(cdecl)
        else:
            self.namespaced_name = ConvertUtils.get_namespaced_name(decl)
            displayname = declDisplayName

        self.name = displayname
        self.lua_name = ConvertUtils.transTypeNameToLua(self.namespaced_name)

        if self.namespaced_name not in allTypes:
            assert(decl.spelling == cdecl.spelling, decl.spelling + '|' + cdecl.spelling)
            assert(decl.displayname == cdecl.displayname, decl.displayname + '|' + cdecl.displayname)

            # CursorKind.ENUM_DECL ENUM_DECL TYPE_ALIAS_DECL TYPEDEF_DECL NO_DECL_FOUND
            if decl.kind == cdecl.kind and ntype.kind == cntype.kind:
                print('@@@ type', self.namespaced_name, decl.kind, ntype.kind)
            else:
                print('@@@ type', self.namespaced_name, decl.kind, ntype.kind, '|', cdecl.kind, cntype.kind)
            allTypes[self.namespaced_name] = self

        if cdecl.kind == cindex.CursorKind.NO_DECL_FOUND:
            if cntype.kind in numberTypes:
                self.name = numberTypes[cntype.kind]
                self.is_numeric = True
                self.lua_name = 'number'
            elif cntype.kind == cindex.TypeKind.BOOL:
                self.name = "bool"
                self.is_boolean = True
                self.lua_name = 'boolean'
            elif cntype.kind == cindex.TypeKind.VOID:
                self.is_void = True
                self.name = "void"
                self.lua_name = 'void'
            elif cntype.kind == cindex.TypeKind.ENUM:
                self.is_enum = True
            else:
                print('invalid type kind', cntype.kind, declDisplayName, cdeclDisplayName)
                self.not_supported = True
        elif cdecl.kind == cindex.TypeKind.MEMBERPOINTER:
            # 不支持类成员函数
            print('invalid TypeKind.MEMBERPOINTER', self)
            self.not_supported = True
        else:
            self._tryParseNSName()

    @staticmethod
    def from_type(ntype):
        cntype = ntype.get_canonical()
        if cntype.kind == cindex.TypeKind.POINTER:
            nt = NativeType.from_type(cntype.get_pointee())
            nt.is_pointer = True
            nt.whole_name = nt.namespaced_name + ' *'

            nt.is_const = cntype.get_pointee().is_const_qualified()
            if nt.is_const:
                nt.whole_name = "const " + nt.whole_name

            if nt.is_numeric:
                nt.is_numeric = False
                if nt.name == 'char':
                    nt.is_string = True
                    nt.lua_name = 'string'
                else:
                    # 数值的指针只支持 char *
                    nt.not_supported = True
        elif cntype.kind == cindex.TypeKind.LVALUEREFERENCE:
            nt = NativeType.from_type(cntype.get_pointee())
            nt.is_reference = True
            nt.whole_name = nt.namespaced_name + ' &'

            nt.is_const = cntype.get_pointee().is_const_qualified()
            if nt.is_const:
                nt.whole_name = "const " + nt.whole_name
        else:
            nt = NativeType()
            nt._initWithType(ntype)
        return nt

    def _initWithTypeStr(self, typename):
        self.whole_name = typename

        constIdx = typename.find('const ')
        if constIdx != -1:
            self.is_const = True
            typename = typename[6:]

        if typename[-2:] == ' &':
            self.is_reference = True
            typename = typename[:-2]
        if typename[-2:] == ' *':
            self.is_pointer = True
            typename = typename[:-2]

        if typename in _numberTypeset:
            self.is_numeric = True
            self.lua_name = 'number'
        elif typename == 'char' and self.is_pointer:
            self.is_string = True
            self.lua_name = 'string'
        elif typename == 'void':
            self.is_void = True
            self.lua_name = 'void'
        elif typename == 'bool':
            self.is_boolean = True
            self.lua_name = 'boolean'
        else:
            self.namespaced_name = typename
            self.lua_name = ConvertUtils.transTypeNameToLua(typename)
            self._tryParseNSName()

    def _tryParseNSName(self):
        if self.namespaced_name in _stringTypes:
            self.is_string = True
            self.lua_name = 'string'
            return

        for parseFun in _arrayParseFun:
            isArray, arrayType = parseFun(self.namespaced_name, self.name)
            if isArray:
                self.is_array = True
                self.array_ele_type = arrayType
                self.lua_name = arrayType.lua_name + '[]'
                return

        for parseFun in _tableParseFun:
            isTable, tableType = parseFun(self.namespaced_name, self.name)
            if isTable:
                self.is_table = True
                self.table_ele_type = tableType
                self.lua_name = 'table<string, %s>' % tableType.lua_name
                return

        # parse function
        self.is_function, self.ret_type, self.param_types = _tryParseFunction(self.namespaced_name, self.name)
        if self.is_function:
            name = ['fun(']
            i = 1
            for arg in self.param_types:
                if i > 1:
                    name.append(', ')
                name.append('p%d: ' % i)
                name.append(arg.lua_name)
                i += 1

            # 不输出返回值，不然生成的 desc 有些不是最后一个参数会不合语法
            name.append(')')

            self.lua_name = ''.join(name)
        else:
            # parse class
            self.is_class = True


    @staticmethod
    def from_type_str(typename):
        ret = NativeType()
        ret._initWithTypeStr(typename)
        return ret

    def __str__(self):
        return self.whole_name

    @property
    def luaType(self):
        return self.lua_name

    @property
    def isNotSupported(self):
        if self.not_supported:
            return True
        
        if self.is_function:
            for p in self.param_types:
                if p.isNotSupported:
                    return True
            
            if self.ret_type.isNotSupported:
                return True

        return False

    def testUseTypes(self, useTypes):
        if self.is_function:
            self.ret_type.testUseTypes(useTypes)
            for param in self.param_types:
                param.testUseTypes(useTypes)
        elif self.namespaced_name not in useTypes:
            print('use type', self.namespaced_name)
            useTypes.add(self.namespaced_name)
            if self.namespaced_name in ConvertUtils.parsedStructs:
                # 被类使用到的 struct 里面嵌套的 struct 也会被使用到， 只靠扫表层会查不全
                print('### parsedStructs', self.namespaced_name)
                ConvertUtils.parsedStructs[self.namespaced_name].testUseTypes(useTypes)
