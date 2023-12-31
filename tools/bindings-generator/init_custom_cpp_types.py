# 注册 c++ 自定义类型到 lua 数据结构的转换， 没有注册的一律不识别
from NativeType import regStringType
from NativeType import regArrayType
from NativeType import regTableType

strNsNameSet = set([
    'std::basic_string<char>',
    'std::basic_string_view<char>',
    'ax::Data',
])
def strType(nsName):
    if nsName in strNsNameSet:
        def genPushCode(tp, varName):
            return 'Tolua::push(L, %s);' % (varName, )
        def genGetCode(self, loc, varName, bDeclareVar):
            ret = []
            if bDeclareVar:
                ret.append('%s %s;' % (self.cppDeclareTypeName, varName))
            ret.append('Tolua::get(L, %d, %s);' % (loc, varName))
            return ''.join(ret)

        return True, genGetCode, genPushCode
    else:
        return False, None, None



def init():
    print('init type')
    regStringType(strType)
