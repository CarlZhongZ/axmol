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
from Fields import NativeOverloadedFunction
from Fields import NativeField

class NativeClass(object):
    def __init__(self, cursor, generator):
        # the cursor to the implementation
        self.cursor = cursor
        self.class_name = cursor.displayname
        self.is_ref_class = self.class_name == "Ref"
        self.namespaced_class_name = self.class_name
        self.parents = []
        self.fields = []
        self.public_fields = []
        self.methods = {}
        self.static_methods = {}
        self.generator = generator
        self.is_abstract = self.class_name in generator.abstract_classes
        self._current_visibility = cindex.AccessSpecifier.PRIVATE
        #for generate lua api doc
        self.override_methods = {}
        self.has_constructor  = False
        self.namespace_name   = ""

        registration_name = generator.get_class_or_rename_class(self.class_name)
        if generator.remove_prefix:
            self.target_class_name = re.sub('^' + generator.remove_prefix, '', registration_name)
        else:
            self.target_class_name = registration_name
        self.namespaced_class_name = ConvertUtils.get_namespaced_name(cursor)
        self.namespace_name        = ConvertUtils.get_namespace_name(cursor)
        self.parse()

    def parse(self):
        '''
        parse the current cursor, getting all the necesary information
        '''
        print('parse class', self.namespaced_class_name)
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

    def generate_code(self):
        '''
        actually generate the code. it uses the current target templates/rules in order to
        generate the right code
        '''

        if not self.is_ref_class:
            self.is_ref_class = self._is_ref_class()

        for m in self.methods_clean():
            m['impl'].generate_code(self)
        for m in self.static_methods_clean():
            m['impl'].generate_code(self)
        for m in self.override_methods_clean():
            m['impl'].generate_code(self, is_override = True)
        for m in self.public_fields:
            if self.generator.should_bind_field(self.class_name, m.name):
                m.generate_code(self)

        # generate register section
        register = Template(file=os.path.join(self.generator.target, "templates", "register.c.tmpl"),
                            searchList=[{"current_class": self}])
        self.generator.impl_file.write(str(register))
    
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

    def _is_ref_class(self, depth = 0):
        """
        Mark the class as 'ax::Ref' or its subclass.
        """
        # print ">" * (depth + 1) + " " + self.class_name

        for parent in self.parents:
            if parent._is_ref_class(depth + 1):
                return True

        if self.is_ref_class:
            return True

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

            if parent_name == "Ref":
                self.is_ref_class = True

        elif cursor.kind == cindex.CursorKind.FIELD_DECL:
            self.fields.append(NativeField(cursor))
            if self._current_visibility == cindex.AccessSpecifier.PUBLIC and NativeField.can_parse(cursor.type):
                self.public_fields.append(NativeField(cursor))
        elif cursor.kind == cindex.CursorKind.CXX_ACCESS_SPEC_DECL:
            self._current_visibility = cursor.access_specifier
        elif cursor.kind == cindex.CursorKind.CXX_METHOD and ConvertUtils.get_availability(cursor) != ConvertUtils.AvailabilityKind.DEPRECATED:
            # skip if variadic
            if self._current_visibility == cindex.AccessSpecifier.PUBLIC and not cursor.type.is_function_variadic():
                m = NativeFunction(cursor)
                registration_name = self.generator.should_rename_function(self.class_name, m.func_name) or m.func_name
                if m.is_override:
                    if NativeClass._is_method_in_parents(self, registration_name):
                        if not (registration_name in self.override_methods):
                            self.override_methods[registration_name] = m
                        else:
                            previous_m = self.override_methods[registration_name]
                            if isinstance(previous_m, NativeOverloadedFunction):
                                previous_m.append(m)
                            else:
                                self.override_methods[registration_name] = NativeOverloadedFunction([m, previous_m])
                        return False

                if m.static:
                    if not (registration_name in self.static_methods):
                        self.static_methods[registration_name] = m
                    else:
                        previous_m = self.static_methods[registration_name]
                        if isinstance(previous_m, NativeOverloadedFunction):
                            previous_m.append(m)
                        else:
                            self.static_methods[registration_name] = NativeOverloadedFunction([m, previous_m])
                else:
                    if not (registration_name in self.methods):
                        self.methods[registration_name] = m
                    else:
                        previous_m = self.methods[registration_name]
                        if isinstance(previous_m, NativeOverloadedFunction):
                            previous_m.append(m)
                        else:
                            self.methods[registration_name] = NativeOverloadedFunction([m, previous_m])
            return True

        elif self._current_visibility == cindex.AccessSpecifier.PUBLIC and cursor.kind == cindex.CursorKind.CONSTRUCTOR and not self.is_abstract:
            # Skip copy constructor
            if cursor.displayname == self.class_name + "(const " + self.namespaced_class_name + " &)":
                # print("Skip copy constructor: " + cursor.displayname)
                return True

            m = NativeFunction(cursor)
            m.is_constructor = True
            self.has_constructor = True
            if not ('constructor' in self.methods):
                self.methods['constructor'] = m
            else:
                previous_m = self.methods['constructor']
                if isinstance(previous_m, NativeOverloadedFunction):
                    previous_m.append(m)
                else:
                    m = NativeOverloadedFunction([m, previous_m])
                    m.is_constructor = True
                    self.methods['constructor'] = m
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

    def writeLuaDesc(self, f):
        f.write('\n\n-- class:%s' % self.namespaced_class_name)
        if self.parents:
            f.write('\n---@class %s: %s' % (ConvertUtils.transTypeNameToLua(self.namespaced_class_name), ConvertUtils.transTypeNameToLua(self.parents[0].namespaced_class_name)))
        else:
            f.write('\n---@class %s' % (ConvertUtils.transTypeNameToLua(self.namespaced_class_name)))

        for field in self.public_fields:
            field.writeLuaDesc(f)
        for (_, m) in self.methods.items():
            m.writeLuaDesc(f, self)
        for (_, m) in self.static_methods.items():
            m.writeLuaDesc(f, self)
