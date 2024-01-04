# 注册 c++ 自定义类型到 lua 数据结构的转换， 没有注册的一律不识别
from NativeType import NativeType
from NativeType import regStringType
from NativeType import regArrayType
from NativeType import regTableType



def _parseArray(nsName):
    eleType = None
    addMethod = None
    if nsName.startswith('ax::Vector'):
        idx = nsName.find('<')
        if idx != -1:
            eleType = NativeType.from_type_str(nsName[idx + 1:-1])
            addMethod = 'pushBack'
    elif nsName.startswith('std::vector'):
        idx = nsName.find('<')
        if idx != -1:
            eleType = NativeType.from_type_str(nsName[idx + 1:-1])
            addMethod = 'push_back'

    if eleType:
        return True, eleType, addMethod

    return False, None, None

def init():
    print('init type')
    regStringType([
        'ax::Data',
    ])

    regArrayType(_parseArray)
