from clang import cindex
import sys
import yaml
import re
import os
import inspect
import traceback
from Cheetah.Template import Template

import ConvertUtils
from Fields import NativeFunction
from Fields import NativeField

class NativeClass(object):
    def __init__(self, cursor, generator):
        # the cursor to the implementation
        self.cursor = cursor
        self.class_name = cursor.displayname
        self.parents = []
        self.fields = []
        self.public_fields = []
        self.constructors = []
        self.methods = {}
        self.static_methods = {}
        self.generator = generator
        self.is_abstract = self.class_name in generator.abstract_classes
        self._current_visibility = cindex.AccessSpecifier.PRIVATE
        #for generate lua api doc
        self.override_methods = {}

        self.target_class_name = generator.get_class_or_rename_class(self.class_name)
        self.namespace_name        = ConvertUtils.get_namespace_name(cursor)
        self.ns_full_name = ConvertUtils.get_namespaced_name(cursor)
        
        self.parse()

    def parse(self):
        '''
        parse the current cursor, getting all the necesary information
        '''
        print('parse class', self.ns_full_name)
        self._deep_iterate(self.cursor)

    def methods_clean(self):
        '''
        clean list of methods (without the ones that should be skipped)
        '''
        ret = []
        for name, impl in self.methods.items():
            should_skip = False
            if name == 'constructor':
                should_skip = True
            else:
                if self.generator.should_skip(self.class_name, name):
                    should_skip = True
            if not should_skip:
                ret.append({"name": name, "impl": impl})
        return ret

    def static_methods_clean(self):
        '''
        clean list of static methods (without the ones that should be skipped)
        '''
        ret = []
        for name, impl in self.static_methods.items():
            should_skip = self.generator.should_skip(self.class_name, name)
            if not should_skip:
                ret.append({"name": name, "impl": impl})
        return ret

    def override_methods_clean(self):
        '''
        clean list of override methods (without the ones that should be skipped)
        '''
        ret = []
        for name, impl in self.override_methods.items():
            should_skip = self.generator.should_skip(self.class_name, name)
            if not should_skip:
                ret.append({"name": name, "impl": impl})
        return ret
    
    def _deep_iterate(self, cursor=None, depth=0):
        for node in cursor.get_children():
            # print("%s%s - %s" % ("> " * depth, node.displayname, node.kind))
            if self._process_node(node):
                self._deep_iterate(node, depth + 1)

    @staticmethod
    def _is_method_in_parents(current_class, method_name):
        if len(current_class.parents) > 0:
            if method_name in current_class.parents[0].methods:
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

            if not self.class_name in self.generator.classes_have_no_parents:
                if parent_name and parent_name not in self.generator.base_classes_to_skip:
                    #if parent and self.generator.in_listed_classes(parent.displayname):
                    if not (parent.displayname in self.generator.generated_classes):
                        parent = NativeClass(parent, self.generator)
                        self.generator.generated_classes[parent.class_name] = parent
                    else:
                        parent = self.generator.generated_classes[parent.displayname]

                    self.parents.append(parent)

        elif cursor.kind == cindex.CursorKind.FIELD_DECL:
            self.fields.append(NativeField(cursor))
            if self._current_visibility == cindex.AccessSpecifier.PUBLIC and NativeField.can_parse(cursor.type):
                self.public_fields.append(NativeField(cursor))
        elif cursor.kind == cindex.CursorKind.CXX_ACCESS_SPEC_DECL:
            self._current_visibility = cursor.access_specifier
        elif cursor.kind == cindex.CursorKind.CXX_METHOD and ConvertUtils.get_availability(cursor) != ConvertUtils.AvailabilityKind.DEPRECATED:
            # skip if variadic
            if self._current_visibility == cindex.AccessSpecifier.PUBLIC and not cursor.type.is_function_variadic():
                m = NativeFunction(cursor, self)
                registration_name = self.generator.should_rename_function(self.class_name, m.name) or m.name
                if m.is_override:
                    if NativeClass._is_method_in_parents(self, registration_name):
                        return False

                idx = 1
                curName = registration_name
                if m.static:
                    while curName in self.static_methods:
                        curName = '%s_%d' % (registration_name, idx)
                        idx += 1
                    self.static_methods[curName] = m
                else:
                    while curName in self.methods:
                        curName = '%s_%d' % (registration_name, idx)
                        idx += 1
                    self.methods[curName] = m
            return True

        elif self._current_visibility == cindex.AccessSpecifier.PUBLIC and cursor.kind == cindex.CursorKind.CONSTRUCTOR and not self.is_abstract:
            # Skip copy constructor
            if cursor.displayname == self.class_name + "(const " + self.ns_full_name + " &)":
                # print("Skip copy constructor: " + cursor.displayname)
                return True
            self.constructors.append(NativeFunction(cursor, self))

            return True
        # else:
            # print >> sys.stderr, "unknown cursor: %s - %s" % (cursor.kind, cursor.displayname)
        return False

    def testUseTypes(self, useTypes):
        for field in self.public_fields:
            field.testUseTypes(useTypes)
        for (_, method) in self.methods.items():
            method.testUseTypes(useTypes)
        for (_, method) in self.static_methods.items():
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
        for m in self.constructors:
            if not m.isNotSupported:
                return True
        return False
