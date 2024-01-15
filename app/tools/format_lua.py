import re

import common_utils
import lua_utils


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
            parms, arrParms, ret = lua_utils.parseFuncDesc(lines)

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
                            tp = arrParms[i][1]
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
