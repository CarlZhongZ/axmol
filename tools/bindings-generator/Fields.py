from clang import cindex
import re

import ConvertUtils
from NativeType import NativeType

class NativeFunction(object):
    def __init__(self, cursor, cls, bConstructor):
        self.cls = cls
        self.is_constructor = bConstructor
        self.cursor = cursor
        self.name = cursor.spelling
        self.arguments = []
        self.argumtntTips = []
        self.static = cursor.kind == cindex.CursorKind.CXX_METHOD and cursor.is_static_method()
        self.is_override = False
        self.ret_type = NativeType.from_type(cursor.result_type)
        self.comment = self.get_comment(cursor.raw_comment)
        self.lua_func_name = None
        self.is_const = cursor.is_const_method()

        # parse the arguments
        for arg in cursor.get_arguments():
            self.argumtntTips.append(arg.spelling)

        for arg in cursor.type.argument_types():
            nt = NativeType.from_type(arg)
            self.arguments.append(nt)

        found_default_arg = False
        index = -1

        for arg_node in self.cursor.get_children():
            if arg_node.kind == cindex.CursorKind.CXX_OVERRIDE_ATTR:
                self.is_override = True
            if arg_node.kind == cindex.CursorKind.PARM_DECL:
                index += 1
                if ConvertUtils.iterate_param_node(arg_node):
                    found_default_arg = True
                    break

        self.min_args = index if found_default_arg else len(self.arguments)

    def get_comment(self, comment):
        replaceStr = comment

        if comment is None:
            return ""

        regular_replace_list = [
            ("(\\s)*//!",""),
            ("(\\s)*//",""),
            ("(\\s)*/\\*\\*",""),
            ("(\\s)*/\\*",""),
            ("\\*/",""),
            ("\r\n", "\n"),
            ("\n(\\s)*\\*", "\n"),
            ("\n(\\s)*@","\n"),
            ("\n(\\s)*","\n"),
            ("\n(\\s)*\n", "\n"),
            ("^(\\s)*\n",""),
            ("\n(\\s)*$", ""),
            ("\n","<br>\n"),
            ("\n", "\n-- ")
        ]

        for item in regular_replace_list:
            replaceStr = re.sub(item[0], item[1], replaceStr)


        return replaceStr

    def testUseTypes(self, useTypes):
        if self.isNotSupported:
            return

        for arg in self.arguments:
            arg.testUseTypes(useTypes)
        self.ret_type.testUseTypes(useTypes)

    @property
    def luaFieldDesc(self):
        if self.isNotSupported:
            return

        isStatic = self.isStatic
        if isStatic:
            ret = ['---@field %s fun(' % (self.lua_func_name)]
        else:
            ret = ['---@field %s fun(self: %s' % (self.lua_func_name, self.cls.luaClassName)]

        if self.ret_type.isVoid:
            retTypes = []
        else:
            retTypes = [self.ret_type.luaType]
        i = 0
        for arg in self.arguments:
            if arg.isRetParmType:
                retTypes.append(arg.luaType)
                continue

            if i > 0 or not self.isStatic:
                ret.append(', ')
            ret.append('%s: %s' % (self.argumtntTips[i] or 'p%d' % i, arg.luaType))
            i += 1
        ret.append('): ')

        if self.is_constructor:
            assert not retTypes
            ret.append(self.cls.luaClassName)
        elif not retTypes:
            ret.append('void')
        else:
            ret.append(', '.join(retTypes))

        return ''.join(ret)

    @property
    def isNotSupported(self):
        if re.match(r'^operator[ +\-*/=<>!&~\|\^\.\[\]]+', self.name):
            # 不支持函数重载
            return True

        for arg in self.arguments:
            if arg.isNotSupported:
                return True
        
        return self.ret_type.isNotSupported

    def isEqual(self, m):
        if self.name != m.name:
            return False

        if len(self.arguments) != len(m.arguments):
            return False
        if not self.ret_type.isEqual(m.ret_type):
            return False
        
        for i, arg in enumerate(self.arguments):
            if not arg.isEqual(m.arguments[i]):
                return False

        return True

    @property
    def isStatic(self):
        return self.is_constructor or self.static

    @property
    def funcName(self):
        if self.name == 'end':
            return 'endToLua'
        else:
            return self.name

class NativeField(object):
    def __init__(self, cursor, fieldName, typeStr):
        if cursor:
            cursor = cursor.canonical
            self.name = cursor.displayname
            self.ntype  = NativeType.from_type(cursor.type)
        else:
            self.name = fieldName
            self.ntype = NativeType.from_type_str(typeStr)

        # print('Field', self.name, self.ntype.ns_full_name)

    @staticmethod
    def can_parse(ntype):
        if ntype.kind == cindex.TypeKind.UNEXPOSED:
            return False
        return True

    def testUseTypes(self, useTypes):
        self.ntype.testUseTypes(useTypes)

    @property
    def luaFieldDesc(self):
        if self.isNotSupported:
            return

        return '---@field %s %s' %  (self.name, self.ntype.luaType)

    @property
    def isNotSupported(self):
        # field 不支持 lua 映射类型的指针
        return self.ntype.isNotSupported or self.ntype.isBasicTypePointer
