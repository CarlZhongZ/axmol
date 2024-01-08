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
from Fields import NativeField
from Fields import NativeFunction

class NativeStruct(object):
    def __init__(self, cursor):
        # the cursor to the implementation
        self.cursor = cursor
        self.class_name = cursor.displayname
        self.fields = []
        self._current_visibility = cindex.AccessSpecifier.PRIVATE

        self.ns_full_name = ConvertUtils.get_namespaced_name(cursor)
        self.namespace_name        = ConvertUtils.get_namespace_name(cursor)

        print('parse struct', self.ns_full_name)

        for node in self.cursor.get_children():
            if node.kind == cindex.CursorKind.FIELD_DECL:
                self.fields.append(NativeField(node))
            elif cursor.kind == cindex.CursorKind.CXX_METHOD:
                if ConvertUtils.isValidMethod(cursor):
                    m = NativeFunction(cursor, self, False)

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
            elif cursor.kind == cindex.CursorKind.CONSTRUCTOR:
                if ConvertUtils.isValidConstructor(cursor):
                    self.constructors.append(NativeFunction(cursor, self, True))
            elif cursor.kind == cindex.CursorKind.VAR_DECL:
                # class static var
                # ax::Vec2::ONE
                pass

    def testUseTypes(self, useTypes):
        for field in self.fields:
            field.testUseTypes(useTypes)

    @property
    def isNotSupported(self):
        for field in self.fields:
            if field.isNotSupported:
                return True
        return False

    def containsType(self, typeName):
        for field in self.fields:
            if field.containsType(typeName):
                return True
        return False

    @property
    def luaNSName(self):
        return ConvertUtils.nsNameToLuaName(self.ns_full_name)

    @property
    def luaClassName(self):
        return ConvertUtils.transTypeNameToLua(self.ns_full_name)
