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

INVALID_NATIVE_TYPE = "??"

voidType = cindex.TypeKind.VOID

booleanType = cindex.TypeKind.BOOL

enumType = cindex.TypeKind.ENUM

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

stringTypes = set([
    'std::basic_string_view<char>',
    'std::basic_string<char>',
])

class NativeType(object):
    def __init__(self):
        self.not_supported = False

        self.is_native_gc_obj = False
        self.is_auto_gc_obj = False

        self.is_void = False
        self.is_boolean = False
        self.is_enum = False
        self.is_numeric = False
        self.is_string = False

        self.is_table = False

        self.is_array = False
        self.array_ele_type = ''

        self.is_function = False
        self.param_types = []
        self.ret_type = None

        self.namespaced_name = '' # with namespace and class name
        self.namespace_name  = '' # only contains namespace
        self.name = ''
        self.decorator = ''
        self.whole_name = ''
        self.lua_name = ''

        self.is_const = False
        self.is_pointer = False
        self.is_reference = False

    def _initWithType(self, ntype):
        decl = ntype.get_declaration()

        cntype = ntype.get_canonical()
        cdecl = cntype.get_declaration()

        declDisplayName = decl.displayname
        cdeclDisplayName = cdecl.displayname
        if len(cdeclDisplayName) > 0 and cdeclDisplayName != declDisplayName:
            displayname = cdeclDisplayName
            self.namespaced_name = ConvertUtils.get_namespaced_name(cdecl)
        else:
            self.namespaced_name = ConvertUtils.get_namespaced_name(decl)
            displayname = declDisplayName
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
            elif cntype.kind == booleanType:
                self.name = "bool"
                self.is_boolean = True
                self.lua_name = 'boolean'
            elif cntype.kind == voidType:
                self.is_void = True
                self.name = "void"
                self.lua_name = 'void'
            elif cntype.kind == enumType:
                self.is_enum = True
                self.name = displayname
                self.lua_name = ConvertUtils.transTypeNameToLua(self.namespaced_name)
        elif cdecl.kind == cindex.TypeKind.MEMBERPOINTER:
            # 不支持类成员函数
            self.name = displayname
            self.not_supported = True
        else:
            self.name = cdecl.displayname
            if self.name in stringTypes:
                self.is_string = True
                self.lua_name = 'string'
            elif self.name.startswith('std::vector<'):
                self.is_array = True
                self.array_ele_type = NativeType.from_type(self.name[12:-1])



    @staticmethod
    def from_type(ntype):
        cntype = ntype.get_canonical()
        if cntype.kind == cindex.TypeKind.POINTER:
            nt = NativeType.from_type(cntype.get_pointee())

            nt.decorator += '*'
            nt.whole_name = nt.namespaced_name + nt.decorator

            nt.is_const = cntype.get_pointee().is_const_qualified()
            nt.is_pointer = True
            if nt.is_const:
                nt.whole_name = "const " + nt.whole_name

            if len(nt.decorator) > 1:
                nt.not_supported = True
        elif cntype.kind == cindex.TypeKind.LVALUEREFERENCE:
            nt = NativeType.from_type(cntype.get_pointee())

            nt.decorator += '&'
            nt.whole_name = nt.namespaced_name + nt.decorator

            nt.is_const = cntype.get_pointee().is_const_qualified()
            if nt.is_const:
                nt.whole_name = "const " + nt.whole_name

            if len(nt.decorator) > 1:
                nt.not_supported = True
        else:
            nt = NativeType()
            nt._initWithType(ntype)
        return nt

    @staticmethod
    def from_type_str(typename):
        pass

    def __str__(self):
        return self.whole_name

    @property
    def luaType(self):
        return self.lua_name

    @property
    def isNotSupported(self):
        return self.not_supported

    def testUseTypes(self, useTypes):
        if self.is_function:
            self.ret_type.testUseTypes(useTypes)
            for param in self.param_types:
                param.testUseTypes(useTypes)
        else:
            namespaced_name = self.namespaced_name
            if namespaced_name not in useTypes:
                # 嵌套扫依赖的 struct
                useTypes.add(namespaced_name)
                if namespaced_name in ConvertUtils.generator.parseStructs:
                    ConvertUtils.generator.parseStructs[namespaced_name].testUseTypes(useTypes)
