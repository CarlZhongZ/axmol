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

class NativeStruct(object):
    def __init__(self, cursor):
        # the cursor to the implementation
        self.cursor = cursor
        self.class_name = cursor.displayname
        self.namespaced_class_name = None
        self.fields = []
        self._current_visibility = cindex.AccessSpecifier.PRIVATE

        self.namespaced_class_name = ConvertUtils.get_namespaced_name(cursor)
        self.namespace_name        = ConvertUtils.get_namespace_name(cursor)

        print('parse struct', self.namespaced_class_name)
        self._deep_iterate(self.cursor, 0)

    def _deep_iterate(self, cursor=None, depth=0):
        for node in cursor.get_children():
            #print("%s%s - %s" % ("> " * depth, node.displayname, node.kind))
            if self._process_node(node):
                self._deep_iterate(node, depth + 1)

    def _process_node(self, node):
        if node.kind == cindex.CursorKind.FIELD_DECL:
            self.fields.append(NativeField(node))

    def testUseTypes(self, useTypes):
        for field in self.fields:
            field.testUseTypes(useTypes)

    def writeLuaDesc(self, f):
        f.write('\n\n\n---@class %s' %  ConvertUtils.transTypeNameToLua(self.namespaced_class_name))
        for field in self.fields:
            field.writeLuaDesc(f)

    @property
    def isNotSupported(self):
        for field in self.fields:
            if field.isNotSupported:
                return True
        return False
