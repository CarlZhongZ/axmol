from clang import cindex
import sys
import yaml
import re
import os
import inspect
import traceback
from Cheetah.Template import Template

import ConvertUtils

allTypes = {}

INVALID_NATIVE_TYPE = "??"

voidType = cindex.TypeKind.VOID

booleanType = cindex.TypeKind.BOOL

enumType = cindex.TypeKind.ENUM

numberTypes = {
    cindex.TypeKind.CHAR_U      : "unsigned char",
    cindex.TypeKind.UCHAR       : "unsigned char",
    cindex.TypeKind.CHAR16      : "char",
    cindex.TypeKind.CHAR32      : "char",
    cindex.TypeKind.USHORT      : "unsigned short",
    cindex.TypeKind.UINT        : "unsigned int",
    cindex.TypeKind.ULONG       : "unsigned long",
    cindex.TypeKind.ULONGLONG   : "unsigned long long",
    cindex.TypeKind.CHAR_S      : "char",
    cindex.TypeKind.SCHAR       : "char",
    cindex.TypeKind.WCHAR       : "wchar_t",
    cindex.TypeKind.SHORT       : "short",
    cindex.TypeKind.INT         : "int",
    cindex.TypeKind.LONG        : "long",
    cindex.TypeKind.LONGLONG    : "long long",
    cindex.TypeKind.FLOAT       : "float",
    cindex.TypeKind.DOUBLE      : "double",
    cindex.TypeKind.LONGDOUBLE  : "long double",
}


class NativeType(object):
    def __init__(self):
        self.not_supported = False

        self.is_native_gc_obj = False
        self.is_auto_gc_obj = False

        self.is_boolean = False
        self.is_enum = False
        self.is_numeric = False

        self.is_function = False
        self.param_types = []
        self.ret_type = None

        self.namespaced_name = None # with namespace and class name
        self.namespace_name  = None # only contains namespace
        self.name = None
        self.whole_name = None

        self.is_const = False
        self.is_pointer = False

        self.canonical_type = None

        self.nsName = None
        self.lua_type = None

    def _initWithType(self, ntype):
        decl = ntype.get_declaration()
        cntype = ntype.get_canonical()
        cdecl = cntype.get_declaration()

        self.canonical_type = NativeType.from_type(ntype.get_canonical())
        nsName = ConvertUtils.get_namespaced_name(decl)
        self.nsName = nsName
        self.namespaced_name = nsName

        if nsName not in allTypes:
            assert(decl.spelling == cdecl.spelling, decl.spelling + '|' + cdecl.spelling)
            assert(decl.displayname == cdecl.displayname, decl.displayname + '|' + cdecl.displayname)

            # CursorKind.ENUM_DECL ENUM_DECL TYPE_ALIAS_DECL TYPEDEF_DECL NO_DECL_FOUND
            if decl.kind == cdecl.kind and ntype.kind == cntype.kind:
                print('@@@ type', nsName, decl.kind, ntype.kind)
            else:
                print('@@@ type', nsName, decl.kind, ntype.kind, '|', cdecl.kind, cntype.kind)
            allTypes[nsName] = self

            if cdecl.kind == cindex.CursorKind.NO_DECL_FOUND:
                if cntype.kind in numberTypes:
                    self.name = numberTypes[cntype.kind]
                elif cntype.kind == booleanType:
                    self.name = "bool"
                    self.lua_type = 'boolean'
                elif cntype.kind == voidType:
                    self.name = "void"
                    self.lua_type = 'void'
                elif cntype.kind == enumType:
                    self.name = decl.displayname


            if decl.kind == cindex.CursorKind.CLASS_DECL \
                and not nt.namespaced_name.startswith('std::function') \
                and not nt.namespaced_name.startswith('std::string') \
                and not nt.namespaced_name.startswith('std::basic_string') \
                and not nt.namespaced_name.startswith('std::string_view') \
                and not nt.namespaced_name.startswith('std::basic_string_view') \
                and not nt.namespaced_name.startswith('std::__thread_id') \
                and not nt.namespaced_name.startswith('cxx17::string_view') \
                and not nt.namespaced_name.startswith('cxx17::basic_string_view'):
                nt.is_object = True
                nt.name = ConvertUtils.normalize_type_str(decl.displayname.replace('::__ndk1', ''))
                nt.namespaced_name = ConvertUtils.normalize_type_str(nt.namespaced_name)
                nt.namespace_name = ConvertUtils.get_namespace_name(decl)
                nt.whole_name = nt.namespaced_name
            else:
                if decl.kind == cindex.CursorKind.NO_DECL_FOUND:
                    nt.name = ConvertUtils.native_name_from_type(ntype)
                else:
                    nt.name = decl.spelling
                nt.namespace_name = ConvertUtils.get_namespace_name(decl)

                if len(nt.namespaced_name) > 0:
                    nt.namespaced_name = ConvertUtils.normalize_type_str(nt.namespaced_name)

                if nt.namespaced_name.startswith("std::function"):
                    nt.name = "std::function"

                if len(nt.namespaced_name) == 0 or nt.namespaced_name.find("::") == -1:
                    nt.namespaced_name = nt.name

                nt.whole_name = nt.namespaced_name
                nt.is_const = ntype.is_const_qualified()
                if nt.is_const:
                    nt.whole_name = "const " + nt.whole_name

                # Check whether it's a std::function typedef
                cdecl = ntype.get_canonical().get_declaration()
                if None != cdecl.spelling and cdecl.spelling == "function":
                    nt.name = "std::function"

                if nt.name != INVALID_NATIVE_TYPE and nt.name != "std::string" and nt.name != "std::function" and nt.name != "cxx17::string_view":
                    if ntype.kind == cindex.TypeKind.UNEXPOSED or ntype.kind == cindex.TypeKind.TYPEDEF or ntype.kind == cindex.TypeKind.ELABORATED:
                        ret = NativeType.from_type(ntype.get_canonical())
                        if ret.name != "":
                            if decl.kind == cindex.CursorKind.TYPEDEF_DECL or decl.kind == cindex.CursorKind.TYPE_ALIAS_DECL:
                                ret.canonical_type = nt
                                # canonical_type 是 typedef 右侧的类型
                                # print('@@@@@@@@@@ canonical_type comp', ret.name, nt.name)
                            return ret

                nt.is_enum = ntype.get_canonical().kind == cindex.TypeKind.ENUM

                if nt.name == "std::function":
                    nt.is_object = False
                    lambda_display_name = ConvertUtils.get_namespaced_name(cdecl)
                    lambda_display_name = lambda_display_name.replace("::__ndk1", "")
                    lambda_display_name = ConvertUtils.normalize_type_str(lambda_display_name)
                    nt.namespaced_name = lambda_display_name
                    r = re.compile('function<([^\\s]+).*\\((.*)\\)>').search(nt.namespaced_name)
                    (ret_type, params) = r.groups()
                    params = filter(None, params.split(", "))

                    nt.is_function = True
                    nt.ret_type = NativeType.from_string(ret_type)
                    nt.param_types = [NativeType.from_string(string) for string in params]

        # mark argument as not supported
        if nt.name == INVALID_NATIVE_TYPE:
            nt.not_supported = True

        if re.search("(char|short|int|long|float|double)$", nt.name) is not None:
            nt.is_numeric = True

    @staticmethod
    def from_type(ntype):
        if ntype.kind == cindex.TypeKind.POINTER:
            nt = NativeType.from_type(ntype.get_pointee())

            if None != nt.canonical_type:
                nt.canonical_type.name += "*"
                nt.canonical_type.namespaced_name += "*"
                nt.canonical_type.whole_name += "*"

            nt.name += "*"
            nt.namespaced_name += "*"
            nt.whole_name = nt.namespaced_name
            nt.is_enum = False
            nt.is_const = ntype.get_pointee().is_const_qualified()
            nt.is_pointer = True
            if nt.is_const:
                nt.whole_name = "const " + nt.whole_name
        elif ntype.kind == cindex.TypeKind.LVALUEREFERENCE:
            nt = NativeType.from_type(ntype.get_pointee())
            nt.is_const = ntype.get_pointee().is_const_qualified()
            nt.whole_name = nt.namespaced_name + "&"

            if nt.is_const:
                nt.whole_name = "const " + nt.whole_name

            if None != nt.canonical_type:
                nt.canonical_type.whole_name += "&"
        else:
            nt = NativeType()
            nt._initWithType(ntype)
        return nt

    @staticmethod
    def from_string(displayname):
        displayname = displayname.replace(" *", "*")

        nt = NativeType()
        nt.name = displayname.split("::")[-1]
        nt.namespaced_name = displayname
        nt.whole_name = nt.namespaced_name
        nt.is_object = True
        return nt

    @property
    def lambda_parameters(self):
        params = ["%s larg%d" % (str(nt), i) for i, nt in enumerate(self.param_types)]
        return ", ".join(params)

    @staticmethod
    def dict_has_key_re(dict, real_key_list):
        for real_key in real_key_list:
            for (k, v) in dict.items():
                if k.startswith('@'):
                    k = k[1:]
                    match = re.match("^" + k + "$", real_key)
                    if match:
                        return True
                else:
                    if k == real_key:
                        return True
        return False

    @staticmethod
    def dict_get_value_re(dict, real_key_list):
        for real_key in real_key_list:
            for (k, v) in dict.items():
                if k.startswith('@'):
                    k = k[1:]
                    match = re.match("^" + k + "$", real_key)
                    if match:
                        return v
                else:
                    if k == real_key:
                        return v
        return None

    @staticmethod
    def dict_replace_value_re(dict, real_key_list):
        for real_key in real_key_list:
            for (k, v) in dict.items():
                if k.startswith('@'):
                    k = k[1:]
                    match = re.match('.*' + k, real_key)
                    if match:
                        return re.sub(k, v, real_key)
                else:
                    if k == real_key:
                        return v
        return None

    def from_native(self, convert_opts):
        assert('generator' in convert_opts)
        generator = convert_opts['generator']
        keys = []

        if self.canonical_type != None:
            keys.append(self.canonical_type.name)
        keys.append(self.name)

        from_native_dict = generator.config['conversions']['from_native']

        if self.is_object:
            if not NativeType.dict_has_key_re(from_native_dict, keys):
                keys.append("object")
        elif self.is_enum:
            keys.append("int")

        if NativeType.dict_has_key_re(from_native_dict, keys):
            tpl = NativeType.dict_get_value_re(from_native_dict, keys)
            tpl = Template(tpl, searchList=[convert_opts])
            return str(tpl).rstrip()

        return "#pragma warning NO CONVERSION FROM NATIVE FOR " + self.name

    def to_native(self, convert_opts):
        assert('generator' in convert_opts)
        generator = convert_opts['generator']
        keys = []

        if self.canonical_type != None:
            keys.append(self.canonical_type.name)
        keys.append(self.name)

        to_native_dict = generator.config['conversions']['to_native']
        if self.is_object:
            if not NativeType.dict_has_key_re(to_native_dict, keys):
                keys.append("object")
        elif self.is_enum:
            keys.append("int")

        if self.is_function:
            tpl = Template(file=os.path.join(generator.target, "templates", "lambda.c.tmpl"),
                searchList=[convert_opts, self])
            indent = convert_opts['level'] * "\t"
            return str(tpl).replace("\n", "\n" + indent)


        if NativeType.dict_has_key_re(to_native_dict, keys):
            tpl = NativeType.dict_get_value_re(to_native_dict, keys)
            tpl = Template(tpl, searchList=[convert_opts])
            return str(tpl).rstrip()
        return "#pragma warning NO CONVERSION TO NATIVE FOR " + self.name + "\n" + convert_opts['level'] * "\t" +  "ok = false"

    def to_string(self, generator):

        if self.name.find("robin_map<std::string, ") == 0:
            self.name = self.name.replace(">", ", hlookup::string_hash, hlookup::equal_to>")
            self.namespaced_name = self.namespaced_name.replace(">", ", hlookup::string_hash, hlookup::equal_to>")
            self.whole_name = self.whole_name.replace(">", ", hlookup::string_hash, hlookup::equal_to>")

        conversions = generator.config['conversions']
        if 'native_types' in conversions:
            native_types_dict = conversions['native_types']
            if NativeType.dict_has_key_re(native_types_dict, [self.namespaced_name]):
                return NativeType.dict_get_value_re(native_types_dict, [self.namespaced_name])

        name = self.namespaced_name

        to_native_dict = generator.config['conversions']['to_native']
        from_native_dict = generator.config['conversions']['from_native']
        use_typedef = False

        typedef_name = self.canonical_type.name if None != self.canonical_type else None

        if None != typedef_name:
            if NativeType.dict_has_key_re(to_native_dict, [typedef_name]) or NativeType.dict_has_key_re(from_native_dict, [typedef_name]):
                use_typedef = True

        if use_typedef and self.canonical_type:
            name = self.canonical_type.namespaced_name
        return "const " + name if (self.is_pointer and self.is_const) else name

    def get_whole_name(self, generator):
        conversions = generator.config['conversions']
        to_native_dict = conversions['to_native']
        from_native_dict = conversions['from_native']
        use_typedef = False
        name = self.whole_name
        typedef_name = self.canonical_type.name if None != self.canonical_type else None

        if None != typedef_name:
            if NativeType.dict_has_key_re(to_native_dict, [typedef_name]) or NativeType.dict_has_key_re(from_native_dict, [typedef_name]):
                use_typedef = True

        if use_typedef and self.canonical_type:
            name = self.canonical_type.whole_name

        to_replace = None
        if 'native_types' in conversions:
            native_types_dict = conversions['native_types']
            to_replace = NativeType.dict_replace_value_re(native_types_dict, [name])

        if to_replace:
            name = to_replace

        if name.find("tsl::robin_map<std::string, ") >= 0:
            name = name.replace(">", ", hlookup::string_hash, hlookup::equal_to>")

        return name

    def object_can_convert(self, generator, is_to_native = True):
        if self.is_object:
            keys = []
            if  self.canonical_type != None:
                keys.append(self.canonical_type.name)
            keys.append(self.name)
            if is_to_native:
                to_native_dict = generator.config['conversions']['to_native']
                if NativeType.dict_has_key_re(to_native_dict, keys):
                    return True
            else:
                from_native_dict = generator.config['conversions']['from_native']
                if NativeType.dict_has_key_re(from_native_dict, keys):
                    return True

        return False

    def __str__(self):
        return self.canonical_type.whole_name if None != self.canonical_type else self.whole_name

    @property
    def luaType(self):
        if self.is_numeric:
            return 'number'
        # if self.is_function:
        #     return 'fun()'
        # elif self.is_object:
        #     if self.canonical_type:
        #         return ConvertUtils.generator.transTypeNameToLua(self.canonical_type.namespaced_name)

        return ConvertUtils.transTypeNameToLua(self.namespaced_name)

    @property
    def isNotSupported(self):
        return self.not_supported

    def testUseTypes(self, useTypes):
        if self.is_function:
            self.ret_type.testUseTypes(useTypes)
            for param in self.param_types:
                param.testUseTypes(useTypes)
        else:
            namespaced_name = self.namespaced_name
            if namespaced_name not in useTypes:
                # 嵌套扫依赖的 struct
                useTypes.add(namespaced_name)
                if namespaced_name in ConvertUtils.generator.parseStructs:
                    ConvertUtils.generator.parseStructs[namespaced_name].testUseTypes(useTypes)