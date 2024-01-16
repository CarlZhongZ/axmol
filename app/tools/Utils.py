from tkinter import Tk
from tkinter import filedialog
from tkinter import colorchooser

from optparse import OptionParser
import base64
import json

import common_utils

def returnResult(v):
    # print(v)
    print(base64.b64encode(json.dumps(v).encode('u8')).decode('u8'))

def getSaveFilePath(title, initialdir, initialfile, filetypes):
    root = Tk()
    root.withdraw()  # 隐藏根窗口

    options = {
        'title': title,
        'initialdir': initialdir,
        'initialfile': initialfile,
        'filetypes': filetypes,
    }

    filePath = filedialog.asksaveasfilename(**options)

    returnResult(filePath)

def getSelectedFilePath(title, initialdir, initialfile, bMultiple, filetypes):
    # 配置对话框选项
    options = {
        'title': title,  # 对话框标题
        'initialdir': initialdir,
        'initialfile': initialfile,
        'multiple': bMultiple,  # 允许选择多个文件
        'filetypes': filetypes,
    }

    # 弹出文件选择对话框
    returnResult(filedialog.askopenfilenames(**options))

def getSaveDirectory(title, initialdir):
    root = Tk()
    root.withdraw()  # 隐藏根窗口

    options = {
        'title': title,
        'initialdir': initialdir,
    }

    directory_path = filedialog.askdirectory(**options)

    returnResult(directory_path)

def chooseColor(title, initialcolor):
    color = colorchooser.askcolor(title=title, initialcolor=initialcolor)
    
    if color != (None, None):
        returnResult(color)
    else:
        returnResult('')


import format_lua
def on_edit_file_changed(fPath, languageId):
    if languageId == 'lua':
        format_lua.formatLua(fPath)

def test(p1, p2, p3):
    returnResult(['@', p1, p2, p3])


# title = 'Save File'
# path = 'C:\\'
# defaultName = 'new_file.txt'
# filter = 'Text Files (*.txt)'

# filePath = winext_getSaveFilePath(title, path, defaultName, filter)
# if filePath:
#     print(f'选择的文件路径：{filePath}')
# else:
#     print('用户取消了选择')


# title = 'Save Directory'
# initialdir = 'C:/DrvPath'

# directory_path = winext_getSaveDirectory(title, initialdir)
# if directory_path:
#     print(f'选择的目录路径：{directory_path}')
# else:
#     print('用户取消了选择')

def test():
    title = 'title'
    initialdir = 'c://'
    initialfile = 'test'
    bMultiple = True
    filetypes = [('Text Files', '.*')]
    # getSaveFilePath(title, initialdir, initialfile, filetypes)
    # getSelectedFilePath(title, initialdir, initialfile, bMultiple, filetypes)
    # getSaveDirectory(title, initialdir, False)
    chooseColor(title, '#ffff00')


def main():
    parser = OptionParser()
    parser.add_option("--callInfo", action="store", dest="callInfo", default=None)
    (opts, args) = parser.parse_args()

    base64data = opts.callInfo

    callInfo = json.loads(base64.b64decode(base64data).decode('u8'))

    globals()[callInfo['functionName']](*callInfo['args'])

if __name__ == '__main__':
    # test()
    main()


