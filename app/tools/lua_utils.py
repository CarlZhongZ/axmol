

import re

def parseFuncDesc(lines):
    parms = {}
    arrParms = []
    returnType = 'void'
    while len(lines) > 0 and re.search(r'^\s*---@', lines[-1]) and not re.search(r'^\s*---@generic', lines[-1]):
        preline = lines.pop()
        mParam = re.match(f'^\\s*---@param ([^ ]+) (.+)$', preline)
        if mParam:
            name = mParam.group(1)
            tp = mParam.group(2)
            parms[name] = tp
            arrParms.append((name, tp))
        mReturn = re.match(f'^\\s*---@return (.+)$', preline)
        if mReturn:
            returnType = mReturn.group(1)

    return parms, arrParms, returnType
