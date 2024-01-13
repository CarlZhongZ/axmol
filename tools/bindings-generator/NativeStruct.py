from clang import cindex

import ConvertUtils
from NativeType import NativeType
from Fields import NativeField
from Fields import NativeFunction

class NativeStruct(object):
    def __init__(self, cursor):
        self.cursor = cursor
        self.class_name = cursor.displayname
        self.parents = []
        self.public_fields = []
        self.constructors = []
        self.static_methods = []
        self.methods = []
        self._current_visibility = cindex.AccessSpecifier.PRIVATE

        self.namespace_name = ConvertUtils.get_namespace_name(cursor)
        self.ns_full_name = ConvertUtils.get_namespaced_name(cursor)

        self.public_static_const_vars = []
        self.is_cpp_struct = True
        self.type = NativeType.from_type_str(self.ns_full_name)

        customizeFieldsInfo = ConvertUtils.costomize_fields.get(self.ns_full_name)
        if customizeFieldsInfo:
            for fieldName, typeStr in customizeFieldsInfo.items():
                self.public_fields.append(NativeField(None, fieldName, typeStr))

        self._parse()

    def _parseMembers(self, node):
        if ConvertUtils.isMethodShouldSkip(self.ns_full_name, node.spelling):
            return

        if node.kind == cindex.CursorKind.FIELD_DECL:
            if not NativeField.can_parse(node.type):
                return
            self.public_fields.append(NativeField(node, None, None))
        elif node.kind == cindex.CursorKind.CXX_METHOD:
            if not ConvertUtils.isValidMethod(node):
                return

            m = NativeFunction(node, self, False)
            if m.is_override:
                if ConvertUtils.isMethodInParents(self, m.name):
                    return

            if m.isStaticMethod:
                for mm in self.static_methods:
                    if mm.isEqual(m):
                        return
                self.static_methods.append(m)
            else:
                for mm in self.methods:
                    if mm.isEqual(m):
                        return
                self.methods.append(m)
        elif node.kind == cindex.CursorKind.CONSTRUCTOR:
            if ConvertUtils.isValidConstructor(node):
                self.constructors.append(NativeFunction(node, self, True))

    def _commonParse(self):
        for node in self.cursor.get_children():
            parent = ConvertUtils.tryParseParent(node)
            if parent:
                self.parents.append(parent)
            elif node.kind == cindex.CursorKind.CXX_ACCESS_SPEC_DECL:
                self._current_visibility = node.access_specifier
            elif self._current_visibility == cindex.AccessSpecifier.PUBLIC:
                if node.kind in ConvertUtils.classOrStructMemberCursorKind:
                    self._parseMembers(node)
                elif node.kind == cindex.CursorKind.VAR_DECL:
                    nt = NativeType.from_type(node.type)
                    if nt.is_const:
                        self.public_static_const_vars.append((node.displayname, nt))
                else:
                    ConvertUtils.tryParseTypes(node)

    # override
    def _parse(self):
        print('parse struct', self.ns_full_name)
        self._current_visibility = cindex.AccessSpecifier.PUBLIC
        self._commonParse()

    def testUseTypes(self, useTypes):
        if self.isNotSupported:
            return

        for field in self.public_fields:
            field.testUseTypes(useTypes)

        for method in self.constructors:
            method.testUseTypes(useTypes)

        for method in self.static_methods:
            method.testUseTypes(useTypes)

        for method in self.methods:
            method.testUseTypes(useTypes)

    @property
    def isNotSupported(self):
        if not self.is_cpp_struct:
            # 创建的 class 都是要支持的
            return False

        for field in self.public_fields:
            if field.isNotSupported:
                return True
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
    def isRefClass(self):
        return not self.is_cpp_struct and self.ns_full_name not in ConvertUtils.non_ref_classes
    
    @property
    def isStruct(self):
        return self.is_cpp_struct

    @property
    def isClass(self):
        return not self.is_cpp_struct

    @property
    def hasConstructor(self):
        if self.isRefClass:
            return False

        for m in self.constructors:
            if not m.isNotSupported:
                return True
        return False

    @property
    def isClassAndHasConstructor(self):
        return not self.is_cpp_struct and self.hasConstructor

    @property
    def validConstructors(self):
        if self.isRefClass:
            # ref class 内存由 cpp 管理， 无法在脚本 new
            return {}

        if not self.constructors and self.isStruct:
            # 对于 struct 没有定义构造函数的给一个默认构造函数
            self.constructors.append(NativeFunction(NativeFunction.noParamConstructorCursor, self, True))

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
    def validFields(self):
        ret = []
        for m in self.public_fields:
            if m.isNotSupported:
                continue
            ret.append(m)

        return ret

    @property
    def parentDeclare(self):
        return self.ns_full_name.rsplit('::', 1)[0]

    @property
    def validStaticConstVars(self):
        ret = []
        for name, tp in self.public_static_const_vars:
            if tp.isNotSupported:
                continue
            ret.append((name, tp))

        return ret
