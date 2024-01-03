# 注册 c++ 自定义类型到 lua 数据结构的转换， 没有注册的一律不识别
from NativeType import regStringType
from NativeType import regArrayType
from NativeType import regTableType


def init():
    print('init type')
    regStringType([
        'ax::Data',
    ])
