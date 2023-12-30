from clang import cindex
import sys
import yaml
import re
import os
import inspect
import traceback
from Cheetah.Template import Template

import ConvertUtils

testLog = open(os.path.join("types.txt"), "wt+", encoding='utf8', newline='\n')
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

_stringParseFun = []
def regStringType(parseFun):
    _stringParseFun.append(parseFun)

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
                c1Count += 1
        else:
            pos1 = parmsStrs.find(c1, cur)
            pos2 = parmsStrs.find(c2, cur)
            assert(pos2 != -1)
            if pos1 != -1 and pos1 < pos2:
                c1Count += 1
                cur = pos1 + 1
            else:
                c1Count -= 1
                cur = pos2 + 1

    print('warning function params not valid:%s' % parmsStrs)

def _tryParseFunction(nsName):
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
        self.is_numeric = False
        self.is_string = False

        self.is_enum = False

        self.is_table = False
        self.table_ele_type = None

        self.is_array = False
        self.array_ele_type = None

        self.is_function = False
        self.param_types = None
        self.ret_type = None

        self.ns_full_name = ''

        self.is_const = False
        self.is_pointer = False
        self.is_reference = False

        self.gen_get_code = None
        self.gen_push_code = None

    def _onParseCodeEndCheck(self, useTypes):
        if self.is_pointer:
            # void* number* 不支持
            if self.is_void or self.is_numeric:
                self.not_supported = True
                return

        ns_full_name = self.ns_full_name
        if self.is_enum:
            assert(ns_full_name in ConvertUtils.parsedEnums, ns_full_name)
        elif self.is_class:
            if ns_full_name in ConvertUtils.parsedEnums:
                # 由字符串创建的 type 不能判定是否为 枚举类型
                self.is_class = False
                self.is_enum = True

        if self.is_enum or self.is_class:
            if self.ns_full_name not in useTypes:
                self.not_supported = True
            elif self.ns_full_name in ConvertUtils.parsedStructs and ConvertUtils.parsedStructs[self.ns_full_name].isNotSupported:
                # struct 是根据节点信息 parse 来的是全的
                self.not_supported = True

    @staticmethod
    def onParseCodeEnd(useTypes):
        for tp in allCreatedTypes:
            tp._onParseCodeEndCheck(useTypes)

    def _initWithType(self, ntype):
        self.is_const = ntype.is_const_qualified()

        decl = ntype.get_declaration()

        cntype = ntype.get_canonical()
        cdecl = cntype.get_declaration()

        nsName = ConvertUtils.get_namespaced_name(decl)
        cnsName = ConvertUtils.get_namespaced_name(cdecl)

        # test write types
        testLog.write('current [%s]: [%s] [%s]\n' % (nsName, decl.kind, ntype.kind))
        testLog.write('canonical [%s]: [%s] [%s]\n' % (cnsName, cdecl.kind, cntype.kind))

        self.ns_full_name = cnsName

        if cdecl.kind == cindex.CursorKind.NO_DECL_FOUND:
            if cntype.kind in numberTypes:
                self.ns_full_name = numberTypes[cntype.kind]
                self.is_numeric = True
            elif cntype.kind == cindex.TypeKind.BOOL:
                self.ns_full_name = "bool"
                self.is_boolean = True
            elif cntype.kind == cindex.TypeKind.VOID:
                self.is_void = True
                self.ns_full_name = 'void'
            elif cntype.kind == cindex.TypeKind.ENUM:
                self.is_enum = True
            else:
                # cindex.TypeKind.MEMBERPOINTER
                # cindex.TypeKind.CONSTANTARRAY
                # cindex.TypeKind.FUNCTIONPROTO
                # cindex.TypeKind.INCOMPLETEARRAY
                self.not_supported = True
        else:
            self._tryParseNSName()

    @staticmethod
    def from_type(ntype):
        cntype = ntype.get_canonical()
        if cntype.kind == cindex.TypeKind.POINTER:
            nt = NativeType.from_type(cntype.get_pointee())
            if nt.is_pointer:
                # 不支持指针的指针
                nt.not_supported = True

            nt.is_pointer = True

            if nt.is_numeric and nt.ns_full_name == 'char':
                # char * 处理
                nt.is_numeric = False
                nt.is_string = True
        elif cntype.kind == cindex.TypeKind.LVALUEREFERENCE:
            nt = NativeType.from_type(cntype.get_pointee())
            nt.is_reference = True
        else:
            nt = NativeType()
            nt._initWithType(ntype)
        return nt

    def _initWithTypeStr(self, typename):
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

        self.ns_full_name = typename

        if typename in _numberTypeset:
            self.is_numeric = True
        elif typename == 'char' and self.is_pointer:
            self.is_string = True
        elif typename == 'void':
            self.is_void = True
        elif typename == 'bool':
            self.is_boolean = True
        else:
            self._tryParseNSName()

    def _tryParseNSName(self):
        if not self.ns_full_name:
            self.not_supported = True
            return

        for parseFun in _stringParseFun:
            isString, genGetCode, genPushCode = parseFun(self.ns_full_name)
            if isString:
                self.is_string = True
                self.gen_get_code = genGetCode
                self.gen_push_code = genPushCode
                return

        for parseFun in _arrayParseFun:
            isArray, arrayType, genGetCode, genPushCode = parseFun(self.ns_full_name)
            if isArray:
                self.is_array = True
                self.array_ele_type = arrayType
                self.gen_get_code = genGetCode
                self.gen_push_code = genPushCode
                return

        for parseFun in _tableParseFun:
            isTable, tableType, genGetCode, genPushCode = parseFun(self.ns_full_name)
            if isTable:
                self.is_table = True
                self.table_ele_type = tableType
                self.gen_get_code = genGetCode
                self.gen_push_code = genPushCode
                return

        # parse function
        self.is_function, self.ret_type, self.param_types = _tryParseFunction(self.ns_full_name)
        if not self.is_function:
            # parse class
            self.is_class = True


    @staticmethod
    def from_type_str(typename):
        ret = NativeType()
        ret._initWithTypeStr(typename)
        return ret

    @property
    def luaType(self):
        if self.is_numeric:
            return 'number'
        elif self.is_string:
            return 'string'
        elif self.is_boolean:
            return 'boolean'
        elif self.is_void:
            return 'void'
        elif self.is_array:
            return self.array_ele_type.luaType + '[]'
        elif self.is_table:
            return  'table<string, %s>' %  self.table_ele_type.luaType
        elif self.is_function:
            name = ['fun(']
            i = 1
            for arg in self.param_types:
                if i > 1:
                    name.append(', ')
                name.append('p%d: ' % i)
                name.append(arg.luaType)
                i += 1

            # 不输出返回值，不然生成的 desc 有些不是最后一个参数会不合语法
            name.append(')')

            return ''.join(name)
        else:
            return ConvertUtils.transTypeNameToLua(self.ns_full_name)

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
        elif self.ns_full_name not in useTypes:
            print('use type', self.ns_full_name)
            useTypes.add(self.ns_full_name)
            if self.ns_full_name in ConvertUtils.parsedStructs:
                # 被类使用到的 struct 里面嵌套的 struct 也会被使用到， 只靠扫表层会查不全
                print('### parsedStructs', self.ns_full_name)
                ConvertUtils.parsedStructs[self.ns_full_name].testUseTypes(useTypes)

    def containsType(self, typeName):
        if typeName == self.ns_full_name:
            return True
            
        if self.is_function:
            for arg in self.param_types:
                if arg.containsType(typeName):
                    return True
            return self.ret_type.containsType(typeName)
        elif self.is_array:
            return self.array_ele_type.containsType(typeName)
        elif self.is_table:
            return self.table_ele_type.containsType(typeName)
        
        return False

    @property
    def cppDeclareTypeName(self):
        if self.is_pointer:
            if self.is_string and self.is_const:
                assert self.ns_full_name == 'char'
                return 'const char *'
            else:
                return self.ns_full_name + ' *'
        else:
            return self.ns_full_name

    def genGetCode(self, loc, varName):
        assert (self.is_pointer or not self.is_void)
        
        if self.gen_get_code:
            return self.gen_get_code(self, loc, varName)
        elif self.is_numeric or self.is_enum:
            return '%s = (%s)lua_tonumber(L, %d);' % (varName, self.cppDeclareTypeName, loc)
        elif self.is_boolean:
            return '%s = lua_toboolean(L, %d);' % (varName, loc)
        elif self.is_string:
            return '%s = lua_tostring(L, %d);' % (varName, loc)
        elif self.is_function:
            # todo...
            return ''
        elif self.is_class:
            if self.is_pointer:
                convertType = '(%s)' % self.cppDeclareTypeName
            else:
                convertType = '*(%s *)' % self.cppDeclareTypeName

            return '%s = %sTolua::tousertype(L, "%s", %d);' % (varName, convertType, self.luaType, loc)

    def genPushCode(self, varName):
        assert (self.is_pointer or not self.is_void)

        if self.gen_push_code:
            return self.gen_push_code(self, varName)
        if self.is_numeric or self.is_enum:
            return 'lua_pushnumber(L, (double)%s);' % (varName, )
        elif self.is_boolean:
            return 'lua_pushboolean(L, %s);' % (varName, )
        elif self.is_string:
            return 'lua_pushstring(L, %s);' % (varName, )
        elif self.is_class:
            if self.is_pointer:
                return 'Tolua::pushusertype(L, (void*)%s, "%s");' % (varName, self.luaType)
            else:
                return 'Tolua::pushusertype(L, (void*)&%s, "%s");' % (varName, self.luaType)

    @property
    def isRefClass(self):
        cls = ConvertUtils.parsedClasses.get(self.ns_full_name)
        if not cls:
            return False
        return cls.isRefClass
