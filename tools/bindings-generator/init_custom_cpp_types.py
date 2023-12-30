# 注册 c++ 自定义类型到 lua 数据结构的转换， 没有注册的一律不识别
from NativeType import regStringType
from NativeType import regArrayType
from NativeType import regTableType

strNsNameSet = set([
    'std::basic_string<char>',
    'std::basic_string_view<char>',
])
def strType(nsName):
    if nsName in strNsNameSet:
        def genPushCode(tp, varName):
            return 'lua_pushlstring(L, %s.data(), %s.length());' % (varName, varName)
        return True, None, genPushCode
    else:
        return False, None, None



def init():
    regStringType(strType)
