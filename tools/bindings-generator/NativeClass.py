from clang import cindex

import ConvertUtils
from NativeStruct import NativeStruct

class NativeClass(NativeStruct):
    def _process_node(self, cursor):
        if cursor.kind == cindex.CursorKind.CXX_BASE_SPECIFIER:
            parent = cursor.get_definition()
            parent_name = parent.displayname

            if parent_name:
                parentNSName = ConvertUtils.get_namespaced_name(parent)
                if parentNSName not in ConvertUtils.parsedClasses:
                    ConvertUtils.parsedClasses[parentNSName] = NativeClass(parent)

                self.parents.append(ConvertUtils.parsedClasses[parentNSName])
        elif cursor.kind == cindex.CursorKind.CXX_ACCESS_SPEC_DECL:
            self._current_visibility = cursor.access_specifier
        elif self._current_visibility == cindex.AccessSpecifier.PUBLIC:
            if cursor.kind in ConvertUtils.classOrStructMemberCursorKind:
                self._parseMembers(cursor)
            else:
                ConvertUtils.tryParseTypes(cursor)

    # override
    def _parse(self):
        print('parse class', self.ns_full_name)
        for node in self.cursor.get_children():
            self._process_node(node)

    @property
    def validFields(self):
        ret = []
        for m in self.public_fields:
            if m.isNotSupported:
                continue
            ret.append(m)

        return ret

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
        return self.ns_full_name not in ConvertUtils.non_ref_classes

    @property
    def isNotSupported(self):
        # 创建的 class 都是要支持的
        return False

    def testUseTypes(self, useTypes):
        for field in self.public_fields:
            field.testUseTypes(useTypes)

        for method in self.constructors:
            method.testUseTypes(useTypes)

        for method in self.static_methods:
            method.testUseTypes(useTypes)

        for method in self.methods:
            method.testUseTypes(useTypes)