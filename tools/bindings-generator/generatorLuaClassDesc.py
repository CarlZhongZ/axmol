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
import json
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
    def __init__(self, config, sec, outdir):
        ConvertUtils.generator = self

        self.index = cindex.Index.create()
        self.outdir = outdir
        with open('code_template/parse_config.json', 'r') as f:
            self.parseConfig = json.loads(f.read())

        self.search_paths = [
            os.path.join(config.get('DEFAULT', 'axdir'), 'core'),
            os.path.join(config.get('DEFAULT', 'axdir'), 'extensions'),
        ]
        self.headers = config.get(sec, 'headers').split(' ')
        self.classes = {}
        classes = re.split(',\n?', config.get(sec, 'classes'))
        for s in classes:
            lists = s.split('[')
            if len(lists) == 2:
                self.classes[lists[0]] = lists[1][:-1].split(' ')

        self.non_ref_classes = set()
        non_ref_classes = re.split(',\n?', config.get(sec, 'non_ref_classes'))
        for s in non_ref_classes:
            lists = s.split('[')
            if len(lists) == 2:
                ns = lists[0]
                for className in lists[1][:-1].split(' '):
                    self.non_ref_classes.add(ns + className)

        self.clang_args = (config.get(sec, 'clang_args') or "").split(" ")
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

        # self.win32_clang_flags = (config.get(sec, 'win32_clang_flags') or "").split(" ") if config.has_option(sec, 'win32_clang_flags') else None,
        # if sys.platform == 'win32' and self.win32_clang_flags != None:
        #     self.clang_args.extend(self.win32_clang_flags)


    def should_rename_function(self, class_name, method_name):
        # 方法名不能为 lua 关键字
        if method_name == 'end':
            return 'endToLua'
        return None

    def in_listed_classes(self, nsName):
        if nsName in self.non_ref_classes:
            return True

        for ns, names in self.classes.items():
            if not nsName.startswith(ns):
                continue
            className = nsName.replace(ns, '')
            for name in names:
                md = re.match("^" + name + "$", className)
                if md:
                    return True

        return False

    def sorted_classes(self):
        sorted_list = []
        for nsName in sorted(ConvertUtils.parsedClasses.keys()):
            nclass = ConvertUtils.parsedClasses[nsName]
            sorted_list += self._sorted_parents(nclass)
        # remove dupes from the list
        no_dupes = []
        [no_dupes.append(i) for i in sorted_list if not no_dupes.count(i)]
        return no_dupes

    def _sorted_parents(self, nclass):
        sorted_parents = []
        for p in nclass.parents:
            sorted_parents += self._sorted_parents(p)
        sorted_parents.append(nclass.ns_full_name)
        return sorted_parents

    def generate_code(self):
        self._parse_headers()

        parsedEnums = ConvertUtils.parsedEnums
        parsedStructs = ConvertUtils.parsedStructs
        parsedClasses = ConvertUtils.parsedClasses

        useTypes = set()
        realUseTypes = set()
        for (_, nativeClass) in parsedClasses.items():
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
                                        'parsedClasses': parsedClasses,
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
                                        'parsedClasses': parsedClasses,
                                    }])))
        
        fAutoConvertCodesH = open(os.path.join(self.outdir, "tolua_auto_convert.h"), "wt+",
                              encoding='utf8', newline='\n')
        fAutoConvertCodesH.write(str(Template(file='code_template/tolua_auto_convert.h.tmpl',
                                    searchList=[self, {
                                        'structTypes': structTypes,
                                        'parsedStructs': parsedStructs,
                                    }])))

        fClassInfo = open(os.path.join("classes.txt"), "wt+", encoding='utf8', newline='\n')
        for _, cls in parsedClasses.items():
            base = cls.parents[0].ns_full_name if cls.parents else 'None'
            fClassInfo.write(f'\n\n\nclass:{cls.ns_full_name} base:{base} isRefClass:{cls.isRefClass}\n')
            for _, m in cls.methods.items():
                fClassInfo.write(f'\t{m.cursor.displayname} {m.isNotSupported}\n')
                fClassInfo.write('\t')
                for t in m.arguments:
                    fClassInfo.write(f'\t{t.ns_full_name}: {t.isNotSupported} {t.not_supported} {t.is_pointer} {t.is_reference} {t.is_class} {t.is_string}')
                fClassInfo.write('\n')

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
        # get the canonical type
        if cursor.kind == cindex.CursorKind.CLASS_DECL:
            if ConvertUtils.isValidDefinition(cursor):
                nsName = ConvertUtils.get_namespaced_name(cursor)
                if self.in_listed_classes(nsName) and nsName not in ConvertUtils.parsedClasses:
                    ConvertUtils.parsedClasses[nsName] = NativeClass(cursor, self)
            return
        elif cursor.kind == cindex.CursorKind.STRUCT_DECL:
            if ConvertUtils.isValidDefinition(cursor):
                nsName = ConvertUtils.get_namespaced_name(cursor)
                if nsName not in ConvertUtils.parsedStructs:
                    ConvertUtils.parsedStructs[nsName] = NativeStruct(cursor)
            return
        elif cursor.kind == cindex.CursorKind.ENUM_DECL:
            if ConvertUtils.isValidDefinition(cursor):
                nsName = ConvertUtils.get_namespaced_name(cursor)
                if nsName not in ConvertUtils.parsedEnums:
                    ConvertUtils.parsedEnums[nsName] = NativeEnum(cursor)
            return

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
        generator = Generator(config, s, outdir)
        generator.generate_code()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
