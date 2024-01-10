from clang import cindex

import ConvertUtils

class NativeEnum(object):
    def __init__(self, cursor):
        # the cursor to the implementation
        self.cursor = cursor
        self.class_name = cursor.displayname
        self.fields = []
        self._current_visibility = cindex.AccessSpecifier.PRIVATE

        self.ns_full_name = ConvertUtils.get_namespaced_name(cursor)
        self.namespace_name        = ConvertUtils.get_namespace_name(cursor)
        
        print('parse enum', self.ns_full_name)
        self._deep_iterate(self.cursor, 0)

    def _deep_iterate(self, cursor=None, depth=0):
        for node in cursor.get_children():
            #print("%s%s - %s" % ("> " * depth, node.displayname, node.kind))
            if self._process_node(node):
                self._deep_iterate(node, depth + 1)

    def _process_node(self, node):
        if node.kind == cindex.CursorKind.ENUM_CONSTANT_DECL:
            field = [node.displayname, node.enum_value]
            # print('fields', field)
            self.fields.append(field)

    @property
    def luaNSName(self):
        return ConvertUtils.nsNameToLuaName(self.ns_full_name)

    @property
    def luaClassName(self):
        return ConvertUtils.transTypeNameToLua(self.ns_full_name)

    @property
    def parentDeclare(self):
        return self.ns_full_name.rsplit('::', 1)[0]

