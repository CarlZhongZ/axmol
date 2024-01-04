from clang import cindex
import sys
import yaml
import re
import os
import inspect
import traceback
from Cheetah.Template import Template

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
        for arg in self.arguments:
            arg.testUseTypes(useTypes)
        self.ret_type.testUseTypes(useTypes)

    @property
    def luaFieldDesc(self):
        if self.isNotSupported:
            return
        
        ret = ['---@field %s fun(self: %s' % (self.name, self.cls.luaClassName)]

        for i in range(self.min_args):
            ret.append(', %s: %s' % (self.argumtntTips[i] or 'p%d' % i, self.arguments[i].luaType))

        for i in range(self.min_args, len(self.arguments)):
            ret.append(', %s?: %s' % (self.argumtntTips[i] or 'p%d' % i, self.arguments[i].luaType))
        ret.append('): ')
        ret.append(self.ret_type.luaType)

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

    def containsType(self, typeName):
        for arg in self.arguments:
            if arg.containsType(typeName):
                return True

        return self.ret_type.containsType(typeName)

class NativeField(object):
    def __init__(self, cursor):
        cursor = cursor.canonical
        self.cursor = cursor
        self.name = cursor.displayname
        self.kind = cursor.type.kind
        self.location = cursor.location
        self.ntype  = NativeType.from_type(cursor.type)
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

    def containsType(self, typeName):
        return self.ntype.containsType(typeName)
