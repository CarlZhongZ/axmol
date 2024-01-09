from clang import cindex
import re

import ConvertUtils
from NativeType import NativeType
from Fields import NativeField
from Fields import NativeFunction

class NativeStruct(object):
    def __init__(self, cursor):
        self.cursor = cursor
        self.class_name = cursor.displayname
        self.parents = []
        self.public_fields = []
        self.constructors = []
        self.static_methods = []
        self.methods = []
        self._current_visibility = cindex.AccessSpecifier.PRIVATE

        self.namespace_name = ConvertUtils.get_namespace_name(cursor)
        self.ns_full_name = ConvertUtils.get_namespaced_name(cursor)

        self.customize_struct_info = None
        self.public_static_const_vars = []

        self._parse()

    def _parseMembers(self, node):
        if ConvertUtils.isMethodShouldSkip(self.ns_full_name, node.spelling):
            return

        if node.kind == cindex.CursorKind.FIELD_DECL:
            if not self.customize_struct_info and NativeField.can_parse(node.type):
                self.public_fields.append(NativeField(node, None, None))
        elif node.kind == cindex.CursorKind.CXX_METHOD:
            if not ConvertUtils.isValidMethod(node):
                return

            m = NativeFunction(node, self, False)
            if m.is_override:
                if ConvertUtils.isMethodInParents(self, m.name):
                    return

            if m.static:
                for mm in self.static_methods:
                    if mm.isEqual(m):
                        return
                self.static_methods.append(m)
            else:
                for mm in self.methods:
                    if mm.isEqual(m):
                        return
                self.methods.append(m)
        elif node.kind == cindex.CursorKind.CONSTRUCTOR:
            if ConvertUtils.isValidConstructor(node):
                self.constructors.append(NativeFunction(node, self, True))

    def _commonParse(self):
        for node in self.cursor.get_children():
            parent = ConvertUtils.tryParseParent(node)
            if parent:
                self.parents.append(parent)
            elif node.kind == cindex.CursorKind.CXX_ACCESS_SPEC_DECL:
                self._current_visibility = node.access_specifier
            elif self._current_visibility == cindex.AccessSpecifier.PUBLIC:
                if node.kind in ConvertUtils.classOrStructMemberCursorKind:
                    self._parseMembers(node)
                elif node.kind == cindex.CursorKind.VAR_DECL:
                    nt = NativeType.from_type(node.type)
                    if nt.is_const:
                        # print('VAR_DECL', node.displayname, nt.fullCppDeclareTypeName)
                        self.public_static_const_vars.append((ConvertUtils.get_namespaced_name(node), nt))
                else:
                    ConvertUtils.tryParseTypes(node)

    # override
    def _parse(self):
        print('parse struct', self.ns_full_name)
        self._current_visibility = cindex.AccessSpecifier.PUBLIC
        self.customize_struct_info = ConvertUtils.costomize_struct.get(self.ns_full_name)
        
        if self.customize_struct_info:
            for fieldName, typeStr in self.customize_struct_info.items():
                self.public_fields.append(NativeField(None, fieldName, typeStr))

        self._commonParse()

    def testUseTypes(self, useTypes):
        if self.isNotSupported:
            return

        for field in self.public_fields:
            field.testUseTypes(useTypes)

        for method in self.constructors:
            method.testUseTypes(useTypes)

        for method in self.static_methods:
            method.testUseTypes(useTypes)

        for method in self.methods:
            method.testUseTypes(useTypes)

    @property
    def isNotSupported(self):
        for field in self.public_fields:
            if field.isNotSupported:
                return True
        return False

    @property
    def luaNSName(self):
        return ConvertUtils.nsNameToLuaName(self.ns_full_name)

    @property
    def luaClassName(self):
        return ConvertUtils.transTypeNameToLua(self.ns_full_name)

    @property
    def validConstructors(self):
        if self.ns_full_name not in ConvertUtils.non_ref_classes:
            return {}

        validStaticMethods  = self.validStaticMethods
        info = {}
        i = 1
        for m in self.constructors:
            if m.isNotSupported:
                continue

            curName = 'new'
            while True:
                if curName in validStaticMethods or curName in info:
                    curName = 'new%d' % i
                    i += 1
                else:
                    break

            info[curName] = m
            m.lua_func_name = curName

        return info

    @property
    def validStaticMethods(self):
        ret = {}
        for m in self.static_methods:
            if m.isNotSupported:
                continue

            m.lua_func_name = m.funcName
            i = 1
            while m.lua_func_name in ret:
                m.lua_func_name = m.funcName + str(i)
                i += 1
            ret[m.lua_func_name] = m

        return ret

    @property
    def validMethods(self):
        ret = {}
        for m in self.methods:
            if m.isNotSupported:
                continue
            
            m.lua_func_name = m.funcName
            i = 1
            while m.lua_func_name in ret:
                m.lua_func_name = m.funcName + str(i)
                i += 1
            ret[m.lua_func_name] = m
        return ret

    @property
    def cppRefName(self):
        return self.ns_full_name.replace('::', '_')
