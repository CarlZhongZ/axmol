import re

import common_utils


reFuncName = r'[a-zA-Z0-9_]+'
reClassFuncName = f'[a-zA-Z0-9]+:{reFuncName}'
reFuncParms = r'\s*\((.*)\)\s*$'
reFuncDeclare = f'^(\\s*)(local\\s+)?function\\s+({reClassFuncName}|{reFuncName}){reFuncParms}'

def formatLua(fPath):
    lines = []
    for line in common_utils.read_utf8_file_lines(fPath):
        # function
        mFunction = re.match(reFuncDeclare, line)
        if mFunction:
            prefixSpace = mFunction.group(1)
            parms = {}
            arrParms = []
            ret = None
            while len(lines) > 0 and re.search(r'^\s*---@', lines[-1]) and not re.search(r'^\s*---@generic', lines[-1]):
                preline = lines.pop()
                mParam = re.match(f'^\\s*---@param ([^ ]+) (.+)$', preline)
                if mParam:
                    tp = mParam.group(2)
                    parms[mParam.group(1)] = tp
                    arrParms.append(tp)
                mReturn = re.match(f'^\\s*---@return (.+)$', preline)
                if mReturn:
                    ret = mReturn.group(1)

            if ret is None:
                ret = 'void'

            # print(mFunction.group(0))
            parmsStr = mFunction.group(4)
            if parmsStr:
                for i, p in enumerate(mFunction.group(4).split(',')):
                    p = p.strip()
                    if p == '...':
                        continue
                    tp = parms.get(p) or parms.get(p + '?')
                    if tp is None:
                        if i < len(arrParms):
                            tp = arrParms[i]
                        elif p.startswith('b'):
                            tp = 'boolean'
                        elif p.startswith('n'):
                            tp = 'number'
                        elif p.startswith('s'):
                            tp = 'String'
                        elif p.startswith('arr'):
                            tp = 'any[]'
                        else:
                            tp = 'any'


                    lines.append(f'{prefixSpace}---@param {p} {tp}\n')
            lines.append(f'{prefixSpace}---@return {ret}\n')

        lines.append(line)

    common_utils.write_utf8_file_content(fPath, ''.join(lines))


if __name__ == '__main__':
    
    fp = r'C:\Users\zhongzuya\Desktop\axmol\app\Content\src\logic\test.lua'
    formatLua(fp)
