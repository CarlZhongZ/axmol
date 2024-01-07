from clang import cindex
import sys
import yaml
import re
import os
import inspect
import traceback
from Cheetah.Template import Template

import ConvertUtils
from NativeStruct import NativeStruct
from NativeEnum import NativeEnum
from Fields import NativeFunction
from Fields import NativeField

class NativeClass(object):
    def __init__(self, cursor, generator):
        self.cursor = cursor
        self.class_name = cursor.displayname
        self.parents = []
        self.public_fields = []
        self.constructors = []
        self.methods = []
        self.static_methods = []
        self.generator = generator
        self._current_visibility = cindex.AccessSpecifier.PRIVATE

        self.namespace_name = ConvertUtils.get_namespace_name(cursor)
        self.ns_full_name = ConvertUtils.get_namespaced_name(cursor)
        
        self.parse()

    def parse(self):
        '''
        parse the current cursor, getting all the necesary information
        '''
        print('parse class', self.ns_full_name)
        for node in self.cursor.get_children():
            self._process_node(node)

    def _shouldSkip(self, name):
        skip_members = ConvertUtils.parseConfig['skip_members']

        info = skip_members.get(self.namespace_name)
        if not info:
            return False

        skipMethods = info.get(self.class_name)
        if skipMethods:
            if name in skipMethods:
                return True
            for reName in skipMethods:
                if re.match(reName, name):
                    return True

        return False

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
    def validFields(self):
        ret = []
        for m in self.public_fields:
            if m.isNotSupported:
                continue
            ret.append(m)

        return ret
    
    @property
    def validConstructors(self):
        if self.ns_full_name not in self.generator.non_ref_classes:
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

    @staticmethod
    def _is_method_in_parents(current_class, method_name):
        if len(current_class.parents) > 0:
            for m in current_class.parents[0].methods:
                if method_name == m.name:
                    return True
            return NativeClass._is_method_in_parents(current_class.parents[0], method_name)
        return False

    def _process_node(self, cursor):
        '''
        process the node, depending on the type. If returns true, then it will perform a deep
        iteration on its children. Otherwise it will continue with its siblings (if any)

        @param: cursor the cursor to analyze
        '''
        if cursor.kind == cindex.CursorKind.CXX_BASE_SPECIFIER:
            parent = cursor.get_definition()
            parent_name = parent.displayname

            if parent_name:
                parentNSName = ConvertUtils.get_namespaced_name(parent)
                if parentNSName not in ConvertUtils.parsedClasses:
                    ConvertUtils.parsedClasses[parentNSName] = NativeClass(parent, self.generator)

                self.parents.append(ConvertUtils.parsedClasses[parentNSName])
        elif cursor.kind == cindex.CursorKind.FIELD_DECL:
            if self._current_visibility == cindex.AccessSpecifier.PUBLIC and NativeField.can_parse(cursor.type) and not self._shouldSkip(cursor.spelling):
                self.public_fields.append(NativeField(cursor))
        elif cursor.kind == cindex.CursorKind.CXX_ACCESS_SPEC_DECL:
            self._current_visibility = cursor.access_specifier
        elif cursor.kind == cindex.CursorKind.CXX_METHOD and ConvertUtils.get_availability(cursor) != ConvertUtils.AvailabilityKind.DEPRECATED:
            # skip if variadic
            if self._current_visibility == cindex.AccessSpecifier.PUBLIC and not cursor.type.is_function_variadic() and not self._shouldSkip(cursor.spelling):
                m = NativeFunction(cursor, self, False)
                if m.is_override:
                    if NativeClass._is_method_in_parents(self, m.name):
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
        elif self._current_visibility == cindex.AccessSpecifier.PUBLIC and cursor.kind == cindex.CursorKind.CONSTRUCTOR:
            # Skip copy constructor
            if cursor.displayname != self.class_name + "(const " + self.ns_full_name + " &)":
                self.constructors.append(NativeFunction(cursor, self, True))
        elif self._current_visibility == cindex.AccessSpecifier.PUBLIC and cursor.kind == cindex.CursorKind.CLASS_DECL:
            if ConvertUtils.isValidDefinition(cursor):
                nsName = ConvertUtils.get_namespaced_name(cursor)
                if self.generator.in_listed_classes(nsName) and nsName not in ConvertUtils.parsedClasses:
                    ConvertUtils.parsedClasses[nsName] = NativeClass(cursor, self.generator)
        elif self._current_visibility == cindex.AccessSpecifier.PUBLIC and cursor.kind == cindex.CursorKind.STRUCT_DECL:
            if ConvertUtils.isValidDefinition(cursor):
                nsName = ConvertUtils.get_namespaced_name(cursor)
                if nsName not in ConvertUtils.parsedStructs:
                    ConvertUtils.parsedStructs[nsName] = NativeStruct(cursor)
        elif self._current_visibility == cindex.AccessSpecifier.PUBLIC and cursor.kind == cindex.CursorKind.ENUM_DECL:
            if ConvertUtils.isValidDefinition(cursor):
                nsName = ConvertUtils.get_namespaced_name(cursor)
                if nsName not in ConvertUtils.parsedEnums:
                    ConvertUtils.parsedEnums[nsName] = NativeEnum(cursor)

    def testUseTypes(self, useTypes):
        for field in self.public_fields:
            field.testUseTypes(useTypes)
        for method in self.methods:
            method.testUseTypes(useTypes)
        for method in self.static_methods:
            method.testUseTypes(useTypes)

    def containsType(self, typeName):
        for field in self.public_fields:
            if field.containsType(typeName):
                return True
            
        for method in self.methods:
            if method.containsType(typeName):
                return True
            
        for method in self.static_methods:
            if method.containsType(typeName):
                return True
            
        if self.parents:
            return self.parents[0].containsType(typeName)

        return False

    @property
    def luaNSName(self):
        return ConvertUtils.nsNameToLuaName(self.ns_full_name)

    @property
    def luaClassName(self):
        return ConvertUtils.transTypeNameToLua(self.ns_full_name)

    @property
    def cppRefName(self):
        return self.ns_full_name.replace('::', '_')
    
    @property
    def hasConstructor(self):
        if self.isRefClass:
            return False

        for m in self.constructors:
            if not m.isNotSupported:
                return True
        return False

    @property
    def isRefClass(self):
        return self.ns_full_name not in self.generator.non_ref_classes
