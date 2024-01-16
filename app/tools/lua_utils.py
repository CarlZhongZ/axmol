import re

reName = r'[a-zA-Z0-9_]+'
reFuncParms = r'\s*\((.*)\)\s*$'
reGlobalFuncDeclare = f'^(\\s*)function\\s+({reName}){reFuncParms}'
reClassFuncName = f'{reName}:{reName}'
reFuncDeclare = f'^(\\s*)(local\\s+)?function\\s+({reClassFuncName}|{reName}){reFuncParms}'
reGlobalVarDeclare = f'^({reName})\\s*=\\s*(.+)'
reLocalVarDeclare = f'^(\\s*)local\\s+({reName})\\s*=\\s*(.+)'
reNumber = r'[0-9.]+'

def parseFuncDesc(lines):
    parms = {}
    arrParms = []
    returnType = 'void'
    while len(lines) > 0 and re.search(r'^\s*---@', lines[-1]) and not re.search(r'^\s*---@generic', lines[-1]):
        preline = lines.pop()
        mParam = re.match(f'^\\s*---@param\\s+({reName}\\??)\\s+([^\\n]+)$', preline)
        if mParam:
            name = mParam.group(1)
            tp = mParam.group(2)
            parms[name] = tp
            arrParms.insert(0, (name, tp))
        mReturn = re.match(f'^\\s*---@return\\s+([^\\n]+)$', preline)
        if mReturn:
            returnType = mReturn.group(1)

    return parms, arrParms, returnType

def parseVarDesc(lines):
    tp = None
    while len(lines) > 0 and re.search(r'^\s*---@type', lines[-1]):
        preline = lines.pop()
        mType = re.match(f'^\\s*---@type (.+)$', preline)
        if mType:
            tp = mType.group(1)

    return tp

def _typeByName(p: str):
    if p.lower().find('name') >=0:
        return 'String'
    elif p in ['func', 'callback']:
        return 'fun(): void'
    elif len(p) > 1 and p[1:2].isupper():
        if p.startswith('b'):
            return 'boolean'
        elif p.startswith('n'):
            return 'number'
        elif p.startswith('s'):
            return 'String'
        elif p.startswith('arr'):
            return 'any[]'

    return 'any'

def _isLuaLiteral(content: str):
    if re.match(reNumber, content) or content in ['true', 'false']:
        return True
    else:
        return False

def tryParseFunction(line: str, lines: list[str]):
    mFunction = re.match(reFuncDeclare, line)
    if not mFunction:
        return False

    prefixSpace = mFunction.group(1)
    parms, arrParms, ret = parseFuncDesc(lines)

    parmsStr = mFunction.group(4)
    if parmsStr:
        for i, p in enumerate(mFunction.group(4).split(',')):
            p = p.strip()
            if p == '...':
                continue

            if p not in parms and p + '?' in parms:
                p = p + '?'
            tp = parms.get(p) or i < len(arrParms) and arrParms[i][1] or _typeByName(p)

            lines.append(f'{prefixSpace}---@param {p} {tp}\n')
    lines.append(f'{prefixSpace}---@return {ret}\n')
    return True

def tryParseGlobalVar(line: str, lines: list[str]):
    mGlobalVar = re.match(reGlobalVarDeclare, line)
    if not mGlobalVar:
        return False

    content = mGlobalVar.group(2)
    if _isLuaLiteral(content):
        return

    preLine = lines[-1]
    if preLine.startswith('---@class ') or preLine.startswith('---@field '):
        return

    tp = parseVarDesc(lines)
    if tp is None:
        if content.startswith("'") or content.startswith('"'):
            tp = 'String'
        else:
            tp = _typeByName(mGlobalVar.group(1))

    lines.append(f'---@type {tp}\n')
