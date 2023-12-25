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

class Generator(object):
    def __init__(self, opts):
        ConvertUtils.generator = self

        self.index = cindex.Index.create()
        self.outdir = opts['outdir']
        print('search_paths=' + opts['search_paths'])
        self.search_paths = opts['search_paths'].split(';')
        self.prefix = opts['prefix']
        self.headers = opts['headers'].split(' ')
        self.classes = opts['classes']
        self.classes_have_no_parents = opts['classes_have_no_parents'].split(' ')
        self.base_classes_to_skip = opts['base_classes_to_skip'].split(' ')
        self.abstract_classes = opts['abstract_classes'].split(' ')
        self.clang_args = opts['clang_args']
        self.target = opts['target']
        self.remove_prefix = opts['remove_prefix']
        self.target_ns = opts['target_ns']
        self.cpp_ns = opts['cpp_ns']
        self.impl_file = None
        self.head_file = None
        self.skip_classes = {}
        self.bind_fields = {}
        self.generated_classes = {}
        self.rename_functions = {}
        self.rename_classes = {}
        self.replace_headers = {}
        self.out_file = opts['out_file']
        self.script_type = opts['script_type']
        self.macro_judgement = opts['macro_judgement']
        self.hpp_headers = opts['hpp_headers']
        self.cpp_headers = opts['cpp_headers']
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
        if opts['field']:
            list_of_fields = re.split(",\n?", opts['field'])
            for field in list_of_fields:
                class_name, fields = field.split("::")
                self.bind_fields[class_name] = []
                match = re.match("\\[([^]]+)\\]", fields)
                if match:
                    self.bind_fields[class_name] = match.group(1).split(" ")
                else:
                    raise Exception("invalid list of bind fields")
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

        if opts['replace_headers']:
            list_of_replace_headers = re.split(",\n?", opts['replace_headers'])
            for replace in list_of_replace_headers:
                header, replaced_header = replace.split("::")
                self.replace_headers[header] = replaced_header

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

    def should_bind_field(self, class_name, field_name, verbose=False):
        if class_name == "*" and "*" in self.bind_fields:
            for func in self.bind_fields["*"]:
                if re.match(func, field_name):
                    return True
        else:
            for key in self.bind_fields.keys():
                if key == "*" or re.match("^" + key + "$", class_name):
                    if verbose:
                        print("%s in bind_fields" % (class_name))
                    if len(self.bind_fields[key]) == 1 and self.bind_fields[key][0] == "*":
                        if verbose:
                            print("All public fields of %s will be bound" % (class_name))
                        return True
                    if field_name != None:
                        for field in self.bind_fields[key]:
                            if re.match(field, field_name):
                                if verbose:
                                    print("Field %s of %s will be bound" % (field_name, class_name))
                                return True
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
        for class_name in self.generated_classes.keys():
            nclass = self.generated_classes[class_name]
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
            if p.class_name in self.generated_classes.keys():
                sorted_parents += self._sorted_parents(p)
        if nclass.class_name in self.generated_classes.keys():
            sorted_parents.append(nclass.class_name)
        return sorted_parents

    def generate_code(self):
        self._parse_headers()
        self.processUsedEnumsAndStructs()
        
        self.impl_file = open(os.path.join(self.outdir, self.out_file + ".cpp"), "wt+", encoding='utf8', newline='\n')
        self.head_file = open(os.path.join(self.outdir, self.out_file + ".hpp"), "wt+", encoding='utf8', newline='\n')

        layout_h = Template(file=os.path.join(self.target, "templates", "layout_head.h.tmpl"),
                            searchList=[self])
        layout_c = Template(file=os.path.join(self.target, "templates", "layout_head.c.tmpl"),
                            searchList=[self])
        self.head_file.write(str(layout_h))
        self.impl_file.write(str(layout_c))

        # 生成类代码
        parsedClass = set()
        for k in self.sorted_classes():
            if k in parsedClass:
                continue
            parsedClass.add(k)
            self.generated_classes[k].generate_code()

        layout_h = Template(file=os.path.join(self.target, "templates", "layout_foot.h.tmpl"),
                            searchList=[self])
        layout_c = Template(file=os.path.join(self.target, "templates", "layout_foot.c.tmpl"),
                            searchList=[self])
        self.head_file.write(str(layout_h))
        self.impl_file.write(str(layout_c))

        self.impl_file.close()
        self.head_file.close()

    # 遍历注册的类, 搜索用到的 enum 和 struct
    def processUsedEnumsAndStructs(self):
        useTypes = set()
        realUseTypes = set()
        for (_, nativeClass) in self.generated_classes.items():
            nativeClass.testUseTypes(useTypes)
            realUseTypes.add(nativeClass.namespaced_class_name)
        
        structTypes = []
        enumTypes = []
        for tp in useTypes:
            if tp in ConvertUtils.parsedEnums:
                enumTypes.append(tp)
                realUseTypes.add(tp)
            elif tp in ConvertUtils.parsedStructs:
                structTypes.append(tp)
                realUseTypes.add(tp)

        NativeType.onParseCodeEnd(realUseTypes)

        structTypes.sort()
        enumTypes.sort()

        fStructConvert = open(os.path.join(self.outdir, self.out_file + "_struct_convert.h"), "wt+",
                              encoding='utf8', newline='\n')
        self.usedStructypes = structTypes
        self.parsedStructs = ConvertUtils.parsedStructs
        fStructConvert.write(str(Template(file=os.path.join(self.target, "templates", "struct_convert.h.tmpl"),
                                    searchList=[self])))

        f = open(os.path.join(self.outdir, self.out_file + ".lua"), "wt+", encoding='utf8', newline='\n')
        for tp in structTypes:
            struct = ConvertUtils.parsedStructs[tp]
            struct.writeLuaDesc(f)



        fEnum = open(os.path.join(self.outdir, self.out_file + "_enum.lua"), "wt+", encoding='utf8', newline='\n')    
        for tp in enumTypes:
            enum = ConvertUtils.parsedEnums[tp]
            enum.writeLuaDesc(f)
            enum.writeLuaEnum(fEnum)

        classes = []
        parsedClass = set()
        for k in self.sorted_classes():
            if k in parsedClass:
                continue
            parsedClass.add(k)
            classes.append(k)

        classes.sort()
        for cls in classes:
            self.generated_classes[cls].writeLuaDesc(f)

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
                    if not (cursor.displayname in self.generated_classes):
                        print('@@@ Class', ConvertUtils.get_namespaced_name(cursor))
                        nclass = NativeClass(cursor, self)
                        self.generated_classes[cursor.displayname] = nclass
        elif cursor.kind == cindex.CursorKind.STRUCT_DECL:
            if cursor == cursor.type.get_declaration() and len(get_children_array_from_iter(cursor.get_children())) > 0:
                if ConvertUtils.isTargetedNamespace(cursor):
                    nsName = ConvertUtils.get_namespaced_name(cursor)
                    if nsName not in ConvertUtils.parsedStructs:
                        print('@@@ Struct', nsName)
                        enum = NativeStruct(cursor)
                        ConvertUtils.parsedStructs[nsName] = enum
        elif cursor.kind == cindex.CursorKind.ENUM_DECL:
            if cursor == cursor.type.get_declaration() and len(get_children_array_from_iter(cursor.get_children())) > 0:
                if ConvertUtils.isTargetedNamespace(cursor):
                    nsName = ConvertUtils.get_namespaced_name(cursor)
                    if nsName not in ConvertUtils.parsedEnums:
                        print('@@@ Enum', nsName)
                        enum = NativeEnum(cursor)
                        ConvertUtils.parsedEnums[nsName] = enum

        for node in cursor.get_children():
            # print("%s %s - %s" % (">" * depth, node.displayname, node.kind))
            self._deep_iterate(node, depth + 1)

    def scriptname_from_native(self, namespace_class_name, namespace_name):
        script_ns_dict = self.config['conversions']['ns_map']
        for (k, v) in script_ns_dict.items():
            if k == namespace_name:
                return namespace_class_name.replace("*","").replace("const ", "").replace(k, v)
        if namespace_class_name.find("::") >= 0:
            if namespace_class_name.find("std::") == 0 or namespace_class_name.find("cxx17::") == 0:
                return namespace_class_name
            if namespace_class_name.find("tsl::") == 0 or namespace_class_name.find("hlookup::") == 0:
                return namespace_class_name
            else:
                raise Exception("The namespace (%s) conversion wasn't set in 'ns_map' section of the conversions.yaml" % namespace_class_name)
        else:
            return namespace_class_name.replace("*","").replace("const ", "")

def main():
    from optparse import OptionParser

    parser = OptionParser("usage: %prog [options] {configfile}")
    parser.add_option("-s", action="store", type="string", dest="section",
                        help="sets a specific section to be converted")
    parser.add_option("-t", action="store", type="string", dest="target",
                        help="specifies the target vm. Will search for TARGET.yaml")
    parser.add_option("-o", action="store", type="string", dest="outdir",
                        help="specifies the output directory for generated C++ code")
    parser.add_option("-n", action="store", type="string", dest="out_file",
                        help="specifcies the name of the output file, defaults to the prefix in the .ini file")

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
        if (opts.section in config.sections()):
            sections = []
            sections.append(opts.section)
        else:
            raise Exception("Section not found in config file")
    else:
        print("processing all sections")
        sections = config.sections()

    # find available targets
    targetdir = os.path.join(workingdir, "targets")
    targets = []
    if (os.path.isdir(targetdir)):
        targets = [entry for entry in os.listdir(targetdir)
                    if (os.path.isdir(os.path.join(targetdir, entry)))]
    if 0 == len(targets):
        raise Exception("No targets defined")

    if opts.target:
        if (opts.target in targets):
            targets = []
            targets.append(opts.target)

    if opts.outdir:
        outdir = opts.outdir
    else:
        outdir = os.path.join(workingdir, "gen")
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    for t in targets:
        # Fix for hidden '.svn', '.cvs' and '.git' etc. folders - these must be ignored or otherwise they will be interpreted as a target.
        if t == ".svn" or t == ".cvs" or t == ".git" or t == ".gitignore":
            continue

        print( "\n.... Generating bindings for target", t)
        for s in sections:
            print( "\n.... .... Processing section", s, "\n")
            gen_opts = {
                'prefix': config.get(s, 'prefix'),
                'headers': config.get(s, 'headers'),
                'replace_headers': config.get(s, 'replace_headers') if config.has_option(s, 'replace_headers') else None,
                'classes': config.get(s, 'classes').split(' '),
                'clang_args': (config.get(s, 'extra_arguments') or "").split(" "),
                'target': os.path.join(workingdir, "targets", t),
                'outdir': outdir,
                'search_paths': os.path.abspath(os.path.join(config.get('DEFAULT', 'axdir'), 'core')) + ";" + os.path.abspath(os.path.join(config.get('DEFAULT', 'axdir'), 'extensions')),
                'remove_prefix': config.get(s, 'remove_prefix'),
                'target_ns': config.get(s, 'target_namespace'),
                'cpp_ns': config.get(s, 'cpp_namespace').split(' ') if config.has_option(s, 'cpp_namespace') else None,
                'classes_have_no_parents': config.get(s, 'classes_have_no_parents'),
                'base_classes_to_skip': config.get(s, 'base_classes_to_skip'),
                'abstract_classes': config.get(s, 'abstract_classes'),
                'skip': config.get(s, 'skip'),
                'field': config.get(s, 'field') if config.has_option(s, 'field') else None,
                'rename_functions': config.get(s, 'rename_functions'),
                'rename_classes': config.get(s, 'rename_classes'),
                'out_file': opts.out_file or config.get(s, 'prefix'),
                'script_type': t,
                'macro_judgement': config.get(s, 'macro_judgement') if config.has_option(s, 'macro_judgement') else None,
                'hpp_headers': config.get(s, 'hpp_headers').split(' ') if config.has_option(s, 'hpp_headers') else None,
                'cpp_headers': config.get(s, 'cpp_headers').split(' ') if config.has_option(s, 'cpp_headers') else None,
                'win32_clang_flags': (config.get(s, 'win32_clang_flags') or "").split(" ") if config.has_option(s, 'win32_clang_flags') else None
                }
            generator = Generator(gen_opts)
            generator.generate_code()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
