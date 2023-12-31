#!/usr/bin/env python
# generator.py
# simple C++ generator, originally targetted for Spidermonkey bindings
#
# Copyright (c) 2011 - Zynga Inc.

from clang import cindex
import sys
import yaml
import re
import os
import inspect
import traceback
from Cheetah.Template import Template

from configparser import ConfigParser

import ConvertUtils
from NativeClass import NativeClass
from NativeEnum import NativeEnum
from NativeStruct import NativeStruct
from NativeType import NativeType

import init_custom_cpp_types

init_custom_cpp_types.init()

class Generator(object):
    def __init__(self, opts):
        ConvertUtils.generator = self

        self.index = cindex.Index.create()
        self.outdir = opts['outdir']
        print('search_paths=' + opts['search_paths'])
        self.search_paths = opts['search_paths'].split(';')
        self.headers = opts['headers'].split(' ')
        self.classes = opts['classes']
        self.classes_have_no_parents = opts['classes_have_no_parents'].split(' ')
        self.base_classes_to_skip = opts['base_classes_to_skip'].split(' ')
        self.abstract_classes = opts['abstract_classes'].split(' ')
        self.clang_args = opts['clang_args']
        self.skip_classes = {}
        self.rename_functions = {}
        self.rename_classes = {}
        self.win32_clang_flags = opts['win32_clang_flags']

        extend_clang_args = []

        for clang_arg in self.clang_args:
            if not os.path.exists(clang_arg.replace("-I","")):
                pos = clang_arg.find("lib/clang/3.3/include")
                if -1 != pos:
                    extend_clang_arg = clang_arg.replace("3.3", "3.4")
                    if os.path.exists(extend_clang_arg.replace("-I","")):
                        extend_clang_args.append(extend_clang_arg)

        if len(extend_clang_args) > 0:
            self.clang_args.extend(extend_clang_args)

        if sys.platform == 'win32' and self.win32_clang_flags != None:
            self.clang_args.extend(self.win32_clang_flags)

        if opts['skip']:
            list_of_skips = re.split(",\n?", opts['skip'])
            for skip in list_of_skips:
                class_name, methods = skip.split("::")
                self.skip_classes[class_name] = []
                match = re.match("\\[([^]]+)\\]", methods)
                if match:
                    self.skip_classes[class_name] = match.group(1).split(" ")
                else:
                    raise Exception("invalid list of skip methods")
        if opts['rename_functions']:
            list_of_function_renames = re.split(",\n?", opts['rename_functions'])
            for rename in list_of_function_renames:
                class_name, methods = rename.split("::")
                self.rename_functions[class_name] = {}
                match = re.match("\\[([^]]+)\\]", methods)
                if match:
                    list_of_methods = match.group(1).split(" ")
                    for pair in list_of_methods:
                        k, v = pair.split("=")
                        self.rename_functions[class_name][k] = v
                else:
                    raise Exception("invalid list of rename methods")

        if opts['rename_classes']:
            list_of_class_renames = re.split(",\n?", opts['rename_classes'])
            for rename in list_of_class_renames:
                class_name, renamed_class_name = rename.split("::")
                self.rename_classes[class_name] = renamed_class_name

    def should_rename_function(self, class_name, method_name):
        if (class_name in self.rename_functions) and (method_name in self.rename_functions[class_name]):
            return self.rename_functions[class_name][method_name]
        return None

    def get_class_or_rename_class(self, class_name):

        if class_name in self.rename_classes:
            return self.rename_classes[class_name]
        return class_name

    def should_skip(self, class_name, method_name, verbose=False):
        if class_name == "*" and "*" in self.skip_classes:
            for func in self.skip_classes["*"]:
                if re.match(func, method_name):
                    return True
        else:
            for key in self.skip_classes.keys():
                if key == "*" or re.match("^" + key + "$", class_name):
                    if verbose:
                        print("%s in skip_classes" % (class_name))
                    if len(self.skip_classes[key]) == 1 and self.skip_classes[key][0] == "*":
                        if verbose:
                            print("%s will be skipped completely" % (class_name))
                        return True
                    if method_name != None:
                        for func in self.skip_classes[key]:
                            if re.match(func, method_name):
                                if verbose:
                                    print("%s will skip method %s" % (class_name, method_name))
                                return True
        if verbose:
            print("%s will be accepted (%s, %s)" % (class_name, key, self.skip_classes[key]))
        return False

    def in_listed_classes(self, class_name):
        """
        returns True if the class is in the list of required classes and it's not in the skip list
        """
        for key in self.classes:
            md = re.match("^" + key + "$", class_name)
            if md and not self.should_skip(class_name, None):
                return True
        return False

    def sorted_classes(self):
        '''
        sorted classes in order of inheritance
        '''
        sorted_list = []
        for class_name in ConvertUtils.parsedClasses.keys():
            nclass = ConvertUtils.parsedClasses[class_name]
            sorted_list += self._sorted_parents(nclass)
        # remove dupes from the list
        no_dupes = []
        [no_dupes.append(i) for i in sorted_list if not no_dupes.count(i)]
        return no_dupes

    def _sorted_parents(self, nclass):
        '''
        returns the sorted list of parents for a native class
        '''
        sorted_parents = []
        for p in nclass.parents:
            if p.class_name in ConvertUtils.parsedClasses.keys():
                sorted_parents += self._sorted_parents(p)
        if nclass.class_name in ConvertUtils.parsedClasses.keys():
            sorted_parents.append(nclass.class_name)
        return sorted_parents

    def generate_code(self):
        self._parse_headers()

        parsedEnums = ConvertUtils.parsedEnums
        parsedStructs = ConvertUtils.parsedStructs

        useTypes = set()
        realUseTypes = set()
        for (_, nativeClass) in ConvertUtils.parsedClasses.items():
            nativeClass.testUseTypes(useTypes)
            realUseTypes.add(nativeClass.ns_full_name)

        enumTypes = []
        structTypes = []
        for tp in useTypes:
            if tp in parsedEnums:
                enumTypes.append(tp)
                realUseTypes.add(tp)
            elif tp in parsedStructs:
                structTypes.append(tp)
                realUseTypes.add(tp)

        NativeType.onParseCodeEnd(realUseTypes)

        validStructs = []
        for tp in structTypes:
            if parsedStructs[tp].isNotSupported:
                continue
            validStructs.append(tp)

        enumTypes.sort()
        validStructs.sort()
        structTypes = validStructs

        # 根据依赖性排序
        dependantSortedStructTypes = []
        for i in range(len(structTypes)):
            tp = structTypes[i]
            for j in range(i):
                if parsedStructs[structTypes[j]].containsType(tp):
                    dependantSortedStructTypes.insert(j, tp)
                    break
            else:
                dependantSortedStructTypes.append(tp)
        structTypes = dependantSortedStructTypes

        classTypes = self.sorted_classes()

        f = open(os.path.join(self.outdir, "engine_types.lua"), "wt+", encoding='utf8', newline='\n')
        f.write(str(Template(file='code_template/engine_types.lua.tmpl',
                                    searchList=[{
                                        'enumTypes': enumTypes,
                                        'parsedEnums' :parsedEnums,
                                        'structTypes': structTypes,
                                        'parsedStructs': parsedStructs,
                                        'classTypes': classTypes,
                                        'parsedClasses': ConvertUtils.parsedClasses,
                                    }])))

        fEnum = open(os.path.join(self.outdir, "engine_enums.lua"), "wt+", encoding='utf8', newline='\n')
        fEnum.write(str(Template(file='code_template/engine_enums.lua.tmpl',
                                    searchList=[{
                                        'enumTypes': enumTypes,
                                        'parsedEnums' :parsedEnums,
                                    }])))

        # gen cpp audo code
        fAutoGenCodesCpp = open(os.path.join(self.outdir, "lua_auto_gen_codes.cpp"), "wt+",
                              encoding='utf8', newline='\n')

        fAutoGenCodesCpp.write(str(Template(file='code_template/lua_auto_gen_codes.cpp.tmpl',
                                    searchList=[self, {
                                        'structTypes': structTypes,
                                        'classTypes': classTypes,
                                        'parsedStructs': parsedStructs,
                                        'parsedClasses': ConvertUtils.parsedClasses,
                                    }])))
        
        fAutoConvertCodesH = open(os.path.join(self.outdir, "tolua_auto_convert.h"), "wt+",
                              encoding='utf8', newline='\n')
        fAutoConvertCodesH.write(str(Template(file='code_template/tolua_auto_convert.h.tmpl',
                                    searchList=[self, {
                                        'structTypes': structTypes,
                                        'parsedStructs': parsedStructs,
                                    }])))

    def _pretty_print(self, diagnostics):
        errors=[]
        for idx, d in enumerate(diagnostics):
            if d.severity > 2:
                errors.append(d)
        if len(errors) == 0:
            return
        print("====\nErrors in parsing headers:")
        severities=['Ignored', 'Note', 'Warning', 'Error', 'Fatal']
        for idx, d in enumerate(errors):
            print("%s. <severity = %s,\n    location = %r,\n    details = %r>" % (
                idx+1, severities[d.severity], d.location, d.spelling))
        print("====\n")

    def _parse_headers(self):
        for header in self.headers:
            print("parsing header => %s" % header)
            tu = self.index.parse(header, self.clang_args)
            if len(tu.diagnostics) > 0:
                self._pretty_print(tu.diagnostics)
                is_fatal = False
                for d in tu.diagnostics:
                    if d.severity >= cindex.Diagnostic.Error:
                        is_fatal = True
                if is_fatal:
                    print("*** Found errors - can not continue")
                    raise Exception("Fatal error in parsing headers")
            self._deep_iterate(tu.cursor)

    def _deep_iterate(self, cursor, depth=0):
        def get_children_array_from_iter(iter):
            children = []
            for child in iter:
                children.append(child)
            return children

        # get the canonical type
        if cursor.kind == cindex.CursorKind.CLASS_DECL:
            if cursor == cursor.type.get_declaration() and len(get_children_array_from_iter(cursor.get_children())) > 0:
                if ConvertUtils.isTargetedNamespace(cursor) and self.in_listed_classes(cursor.displayname):
                    if not (cursor.displayname in ConvertUtils.parsedClasses):
                        nclass = NativeClass(cursor, self)
                        ConvertUtils.parsedClasses[cursor.displayname] = nclass
        elif cursor.kind == cindex.CursorKind.STRUCT_DECL:
            if cursor == cursor.type.get_declaration() and len(get_children_array_from_iter(cursor.get_children())) > 0:
                if ConvertUtils.isTargetedNamespace(cursor):
                    nsName = ConvertUtils.get_namespaced_name(cursor)
                    if nsName not in ConvertUtils.parsedStructs:
                        enum = NativeStruct(cursor)
                        ConvertUtils.parsedStructs[nsName] = enum
        elif cursor.kind == cindex.CursorKind.ENUM_DECL:
            if cursor == cursor.type.get_declaration() and len(get_children_array_from_iter(cursor.get_children())) > 0:
                if ConvertUtils.isTargetedNamespace(cursor):
                    nsName = ConvertUtils.get_namespaced_name(cursor)
                    if nsName not in ConvertUtils.parsedEnums:
                        enum = NativeEnum(cursor)
                        ConvertUtils.parsedEnums[nsName] = enum

        for node in cursor.get_children():
            # print("%s %s - %s" % (">" * depth, node.displayname, node.kind))
            self._deep_iterate(node, depth + 1)

def main():
    from optparse import OptionParser

    parser = OptionParser("usage: %prog [options] {configfile}")
    parser.add_option("-s", action="store", type="string", dest="section",
                        help="sets a specific section to be converted")
    parser.add_option("-o", action="store", type="string", dest="outdir",
                        help="specifies the output directory for generated C++ code")

    (opts, args) = parser.parse_args()

    # script directory
    workingdir = os.path.dirname(inspect.getfile(inspect.currentframe()))

    if len(args) == 0:
        parser.error('invalid number of arguments')

    config = ConfigParser()
    config.read('userconf.ini')
    config.read(args[0])

    print('Using userconfig \n ', config.items('DEFAULT'))

    clang_lib_path = os.path.join(config.get('DEFAULT', 'cxxgeneratordir'), 'libclang')
    cindex.Config.set_library_path(clang_lib_path)

    if (0 == len(config.sections())):
        raise Exception("No sections defined in config file")

    sections = []
    if opts.section:
        for ss in opts.section.split('|'):
            if (ss in config.sections()):
                sections.append(ss)
            else:
                raise Exception("Section not found in config file")
    else:
        print("processing all sections")
        sections = config.sections()

    outdir = opts.outdir
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    print( "\n.... Generating bindings")
    for s in sections:
        print( "\n.... .... Processing section", s, "\n")
        gen_opts = {
            'headers': config.get(s, 'headers'),
            'classes': config.get(s, 'classes').split(' '),
            'clang_args': (config.get(s, 'clang_args') or "").split(" "),
            'classes_have_no_parents': config.get(s, 'classes_have_no_parents'),
            'base_classes_to_skip': config.get(s, 'base_classes_to_skip'),
            'abstract_classes': config.get(s, 'abstract_classes'),
            'skip': config.get(s, 'skip'),
            'rename_functions': config.get(s, 'rename_functions'),
            'rename_classes': config.get(s, 'rename_classes'),
            'win32_clang_flags': (config.get(s, 'win32_clang_flags') or "").split(" ") if config.has_option(s, 'win32_clang_flags') else None,

            'outdir': outdir,
            'search_paths': os.path.abspath(os.path.join(config.get('DEFAULT', 'axdir'), 'core')) + ";" + os.path.abspath(os.path.join(config.get('DEFAULT', 'axdir'), 'extensions')),
            }
        generator = Generator(gen_opts)
        generator.generate_code()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
