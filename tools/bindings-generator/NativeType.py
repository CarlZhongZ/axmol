from clang import cindex
import sys
import yaml
import re
import os
import inspect
import traceback
from Cheetah.Template import Template

import ConvertUtils

testLog = open(os.path.join("configs/types.txt"), "wt+", encoding='utf8', newline='\n')
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

        # c struct 对应 lua 的 table
        self.is_struct = False

        self.is_void = False
        self.is_boolean = False
        self.is_numeric = False
        self.is_string = False

        self.is_enum = False

        self.container_add_method_name = None  # cpp 对象增加元素的方法名称

        self.is_table = False
        self.table_ele_type = None

        self.is_array = False
        self.array_ele_type = None

        self.is_function = False
        self.param_types = None
        self.ret_type = None

        self.ns_full_name = ''

        self.is_const = False
        self.is_pointer = 0
        self.is_reference = 0

        self._customizeLuaType = None

    def _onParseCodeEndCheck(self, useTypes):
        ns_full_name = self.ns_full_name
        if self.is_enum:
            assert(ns_full_name in ConvertUtils.parsedEnums, ns_full_name)
        elif self.is_class:
            if ns_full_name in ConvertUtils.parsedEnums:
                # 由字符串创建的 type 不能判定是否为 枚举类型
                self.is_class = False
                self.is_enum = True
            elif ns_full_name in ConvertUtils.parsedStructs:
                self.is_class = False
                self.is_struct = True

        if self.is_enum or self.is_class or self.is_struct:
            if self.ns_full_name not in useTypes:
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
                assert(cntype.kind == cindex.TypeKind.MEMBERPOINTER or \
                       cntype.kind == cindex.TypeKind.CONSTANTARRAY or \
                        cntype.kind == cindex.TypeKind.FUNCTIONPROTO or \
                            cntype.kind == cindex.TypeKind.INCOMPLETEARRAY, cntype.kind)
                self.not_supported = True
        else:
            self._tryParseNSName()

    @staticmethod
    def from_type(ntype):
        cntype = ntype.get_canonical()
        if cntype.kind == cindex.TypeKind.POINTER:
            nt = NativeType.from_type(cntype.get_pointee())

            nt.is_pointer += 1

            if nt.is_numeric and nt.ns_full_name == 'char' and nt.is_const:
                # char * 处理
                nt.is_numeric = False
                nt.is_string = True
        elif cntype.kind == cindex.TypeKind.LVALUEREFERENCE:
            nt = NativeType.from_type(cntype.get_pointee())
            nt.is_reference += 1
        else:
            nt = NativeType()
            nt._initWithType(ntype)
        return nt

    def _initWithTypeStr(self, typename):
        constIdx = typename.find('const ')
        if constIdx != -1:
            self.is_const = True
            typename = typename[6:]

        for i in range(len(typename)):
            ch = typename[i:i+1]
            if ch == '&':
                self.is_reference += 1
            elif ch == '*':
                self.is_pointer += 1

        if typename[-2:] == ' &':
            typename = typename[:-2]
        if typename[-2:] == ' *':
            typename = typename[:-2]

        self.ns_full_name = typename

        if typename in _numberTypeset:
            if typename == 'char' and self.is_pointer == 1 and self.is_const:
                self.is_string = True
            else:
                self.is_numeric = True
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

        self._customizeLuaType = ConvertUtils.string_types.get(self.ns_full_name)
        if self._customizeLuaType:
            self.is_string = True
            return

        self.is_array, self.array_ele_type, self.container_add_method_name = ConvertUtils.tryParseArrayType(self.ns_full_name)
        if self.is_array:
            return

        self.is_table, self.table_ele_type, self.container_add_method_name = ConvertUtils.tryParseTableType(self.ns_full_name)
        if self.is_table:
            return

        # parse function
        self.is_function, self.ret_type, self.param_types = _tryParseFunction(self.ns_full_name)
        if self.is_function:
            return
        
        self.is_class = True

    @staticmethod
    def from_type_str(typename):
        ret = NativeType()
        ret._initWithTypeStr(typename)
        return ret
    
    def isEqual(self, tp2):
        return self.ns_full_name == tp2.ns_full_name and \
            self.is_pointer == tp2.is_pointer

    @property
    def luaType(self):
        if self._customizeLuaType:
            return self._customizeLuaType

        if self.is_numeric:
            return 'number'
        elif self.is_string:
            return 'String'
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
        
        # 不支持指针的指针
        if self.is_pointer >= 2:
            return True
        
        # void*, num* 不支持
        if (self.is_void or self.is_numeric) and self.is_pointer == 1:
            return True

        if self.is_struct:
            return ConvertUtils.parsedStructs[self.ns_full_name].isNotSupported
        elif self.is_array:
            return self.array_ele_type.isNotSupported
        elif self.is_table:
            return self.table_ele_type.isNotSupported
        elif self.is_function:
            for p in self.param_types:
                if p.isNotSupported:
                    return True
            
            if self.ret_type.isNotSupported:
                return True

        return False

    def testUseTypes(self, useTypes):
        if self.isNotSupported:
            return

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

    @property
    def cppDeclareTypeName(self):
        # 用于定义 lua call cpp 的参数定义
        if self.is_string and self.ns_full_name == 'char':
            return 'const char *'
        elif self.is_class:
            return self.ns_full_name + ' *'
        else:
            return self.ns_full_name

    @property
    def fullCppDeclareTypeName(self):
        # 用于完整的函数声明
        ret = self.ns_full_name
        if self.is_const:
           ret = 'const ' + ret
        if self.is_pointer > 0:
            ret = ret + ' *'
        if self.is_reference > 0:
            ret = ret + ' &'
        return ret

    def genGetCode(self, loc, varName, bDeclareVar):
        assert (not self.isVoid)

        if self.isExtLuaType:
            if self.is_array:
                return str(Template(file='configs/VectorGet.tmpl',
                                    searchList=[self, {
                                        'loc': loc,
                                        'varName': varName,
                                        'bDeclareVar': bDeclareVar,
                                    }]))
            else:
                ret = []
                if bDeclareVar:
                    ret.append('%s %s;' % (self.cppDeclareTypeName, varName))
                ret.append('tolua_get_value(L, %d, %s);' % (loc, varName))
                return ''.join(ret)

        if bDeclareVar:
            varName = '%s %s' % (self.cppDeclareTypeName, varName)

        if self.is_numeric or self.is_enum:
            return '%s = (%s)lua_tonumber(L, %d);' % (varName, self.cppDeclareTypeName, loc)
        elif self.is_boolean:
            return '%s = lua_toboolean(L, %d);' % (varName, loc)
        elif self.is_string:
            return '%s = lua_tostring(L, %d);' % (varName, loc)
        elif self.is_function:
            return str(Template(file='configs/lua_fun_to_std_fun.tmpl',
                                    searchList=[{
                                        'funcType': self,
                                        'varName' :varName,
                                        'loc': loc
                                    }]))
        elif self.is_class:
            if not bDeclareVar and self.is_pointer == 0:
                return '%s = *(%s)Tolua::toType(L, "%s", %d);' % (varName, self.cppDeclareTypeName, self.luaType, loc)
            else:
                return '%s = (%s)Tolua::toType(L, "%s", %d);' % (varName, self.cppDeclareTypeName, self.luaType, loc)

    # bIsCppType: push 的类型是 cpp 原生定义的类型，而不是 get 代码定义的类型
    def genPushCode(self, varName, bIsCppType):
        assert (not self.isVoid)

        if self.isExtLuaType:
            if self.is_array:
                return str(Template(file='configs/VectorPush.tmpl',
                                    searchList=[self, {
                                        'varName': varName,
                                        'bIsCppType': bIsCppType,
                                    }]))
            else: 
                if bIsCppType and self.is_pointer == 1:
                    return 'tolua_push_value(L, *%s);' % (varName, )
                else:
                    return 'tolua_push_value(L, %s);' % (varName, )
        elif self.is_enum:
            assert(self.is_pointer == 0)
            return 'lua_pushnumber(L, (double)%s);' % (varName, )
        elif self.is_numeric:
            if bIsCppType and self.is_pointer == 1:
                return 'lua_pushnumber(L, (double)*%s);' % (varName, )
            else:
                return 'lua_pushnumber(L, (double)%s);' % (varName, )
        elif self.is_boolean:
            if bIsCppType and self.is_pointer == 1:
                return 'lua_pushboolean(L, *%s);' % (varName, )
            else:
                return 'lua_pushboolean(L, %s);' % (varName, )
        elif self.is_string:
            assert(self.is_pointer == 1)  # char *
            return 'lua_pushstring(L, %s);' % (varName, )
        elif self.is_class:
            if self.isRefClass:
                assert(self.is_pointer == 1)
                return 'Tolua::pushRefType(L, (void*)%s, TOLUA_TYPE_NAME(%s), "%s");' % (varName, varName, self.luaType)
            else:
                if bIsCppType and self.is_pointer == 0:
                    return 'Tolua::pushType(L, (void*)new %s(%s), "%s");' % (self.ns_full_name, varName, self.luaType)
                else:
                    return 'Tolua::pushType(L, (void*)new %s(*%s), "%s");' % (self.ns_full_name, varName, self.luaType)

    @property
    def isRefClass(self):
        cls = ConvertUtils.parsedClasses.get(self.ns_full_name)
        if not cls:
            return False
        return cls.isRefClass

    @property
    def isVoid(self):
        return self.is_void and self.is_pointer == 0

    @property
    def retCount(self):
        return 0 if self.isVoid or self.is_function else 1

    @property
    def isExtLuaType(self):
        # 基础扩展类型指针当参数在处理完结果后需要将处理完毕的结果返回
        return self.is_string and self.ns_full_name != 'char' or \
                                        self.is_table or \
                                        self.is_array or \
                                        self.is_struct

    @property
    def isBasicTypePointer(self):
        return (self.isExtLuaType or self.is_numeric or self.is_boolean) and self.is_pointer > 0
    
    @property
    def isClassNoPointer(self):
        return self.is_class and self.is_pointer == 0

    @property
    def isRetParmType(self):
        # 该函数参数的类型是否是作为返回类型
        return not self.is_const and \
                self.ns_full_name in ConvertUtils.parsedStructs and \
                (self.is_pointer == 1 or self.is_reference == 1)
