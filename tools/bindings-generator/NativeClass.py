import ConvertUtils
from NativeStruct import NativeStruct

class NativeClass(NativeStruct):
    # override
    def _parse(self):
        print('parse class', self.ns_full_name)
        self.is_struct = False
        self._commonParse()

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