import ConvertUtils
from NativeStruct import NativeStruct

class NativeClass(NativeStruct):
    # override
    def _parse(self):
        print('parse class', self.ns_full_name)
        self.is_cpp_struct = False
        self._commonParse()
