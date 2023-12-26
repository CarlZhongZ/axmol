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
    def __init__(self, cursor):
        self.cursor = cursor
        self.func_name = cursor.spelling
        self.signature_name = self.func_name
        self.arguments = []
        self.argumtntTips = []
        self.static = cursor.kind == cindex.CursorKind.CXX_METHOD and cursor.is_static_method()
        self.implementations = []
        self.is_overloaded = False
        self.is_constructor = False
        self.is_override = False
        self.ret_type = NativeType.from_type(cursor.result_type)
        self.comment = self.get_comment(cursor.raw_comment)

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

    def generate_code(self, current_class, is_override=False):
        gen = current_class.generator
        config = gen.config

        if self.static:
            self.signature_name = str(Template(config['definitions']['sfunction'],
                                searchList=[current_class, self]))
            tpl = Template(file=os.path.join(gen.target, "templates", "sfunction.c.tmpl"),
                            searchList=[current_class, self])
        else:
            if not self.is_constructor:
                self.signature_name = str(Template(config['definitions']['ifunction'],
                                searchList=[current_class, self]))
            else:
                self.signature_name = str(Template(config['definitions']['constructor'],
                            searchList=[current_class, self]))

            tpl = Template(file=os.path.join(gen.target, "templates", "ifunction.c.tmpl"),
                            searchList=[current_class, self])
        if not is_override:
            gen.impl_file.write(str(tpl))

    def testUseTypes(self, useTypes):
        for arg in self.arguments:
            arg.testUseTypes(useTypes)
        self.ret_type.testUseTypes(useTypes)

    def writeLuaDesc(self, f, cls):
        if self.isNotSupported:
            return

        f.write('\n---@field %s fun(self: %s' % (self.func_name, ConvertUtils.transTypeNameToLua(cls.namespaced_class_name)))
        for i in range(self.min_args):
            f.write(', %s: %s' % (self.argumtntTips[i] or 'p%d' % i, self.arguments[i].luaType))

        for i in range(self.min_args, len(self.arguments)):
            f.write(', %s?: %s' % (self.argumtntTips[i] or 'p%d' % i, self.arguments[i].luaType))
        f.write(')')
        f.write(self.ret_type.luaType)
        f.write(' @ function')

    @property
    def isNotSupported(self):
        if re.match(r'^operator[ +\-*/=<>!&~\|\^\.\[\]]+', self.func_name):
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
    
class NativeOverloadedFunction(object):
    def __init__(self, func_array):
        self.implementations = func_array
        self.func_name = func_array[0].func_name
        self.signature_name = self.func_name
        self.min_args = 100
        self.is_constructor = False
        self.is_overloaded = True
        for m in func_array:
            self.min_args = min(self.min_args, m.min_args)

        self.comment = self.get_comment(func_array[0].cursor.raw_comment)

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

    def append(self, func):
        self.min_args = min(self.min_args, func.min_args)
        self.implementations.append(func)

    def generate_code(self, current_class=None, is_override=False):
        gen = current_class.generator
        config = gen.config

        static = self.implementations[0].static

        if static:
            self.signature_name = str(Template(config['definitions']['sfunction'],
                            searchList=[current_class, self]))
            tpl = Template(file=os.path.join(gen.target, "templates", "sfunction_overloaded.c.tmpl"),
                            searchList=[current_class, self])
        else:
            if not self.is_constructor:
                self.signature_name = str(Template(config['definitions']['ifunction'],
                                searchList=[current_class, self]))
            else:
                self.signature_name = str(Template(config['definitions']['constructor'],
                                searchList=[current_class, self]))
            tpl = Template(file=os.path.join(gen.target, "templates", "ifunction_overloaded.c.tmpl"),
                            searchList=[current_class, self])
        if not is_override:
            gen.impl_file.write(str(tpl))

    def testUseTypes(self, useTypes):
        for fun in self.implementations:
            fun.testUseTypes(useTypes)

    def writeLuaDesc(self, f, cls):
        for impl in self.implementations:
            impl.writeLuaDesc(f, cls)
    
    def containsType(self, typeName):
        for impl in self.implementations:
            if impl.containsType(typeName):
                return True
        return False

class NativeField(object):
    def __init__(self, cursor):
        cursor = cursor.canonical
        self.cursor = cursor
        self.name = cursor.displayname
        self.kind = cursor.type.kind
        self.location = cursor.location
        self.signature_name = self.name
        self.ntype  = NativeType.from_type(cursor.type)
        print('Field', self.name, self.ntype.namespaced_name)

    @staticmethod
    def can_parse(ntype):
        native_type = NativeType.from_type(ntype)
        if ntype.kind == cindex.TypeKind.UNEXPOSED and native_type.name != "std::string" and native_type.name != "cxx17::string_view":
            return False
        return True

    def generate_code(self, current_class = None, generator = None):
        gen = current_class.generator if current_class else generator

        tpl = Template(file=os.path.join(gen.target, "templates", "public_field.c.tmpl"),
                       searchList=[current_class, self])
        gen.impl_file.write(str(tpl))

    def testUseTypes(self, useTypes):
        self.ntype.testUseTypes(useTypes)

    def writeLuaDesc(self, f):
        if self.isNotSupported:
            return

        f.write('\n---@field %s %s' %  (self.name, self.ntype.luaType))
        f.write(' @ field')

    @property
    def isNotSupported(self):
        return self.ntype.isNotSupported

    def containsType(self, typeName):
        return self.ntype.containsType(typeName)
