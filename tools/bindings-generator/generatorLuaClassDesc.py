#!/usr/bin/env python
# generator.py
# simple C++ generator, originally targetted for Spidermonkey bindings
#
# Copyright (c) 2011 - Zynga Inc.

from clang import cindex
import sys
import re
import os
import traceback

from configparser import ConfigParser

import ConvertUtils

class Generator(object):
    def __init__(self, config, sec):
        classes = re.split(',\n?', config.get(sec, 'classes'))
        for s in classes:
            lists = s.split('[')
            if len(lists) == 2:
                ConvertUtils.classes[lists[0]] = lists[1][:-1].split(' ')

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

        ConvertUtils.clang_args = self.clang_args

def main():
    from optparse import OptionParser

    parser = OptionParser("usage: %prog [options] {configfile}")
    parser.add_option("-s", action="store", type="string", dest="section",
                        help="sets a specific section to be converted")

    (opts, args) = parser.parse_args()

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

    print( "\n.... Generating bindings")
    for s in sections:
        print( "\n.... .... Processing section", s, "\n")
        Generator(config, s)

    ConvertUtils.generateCode()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
