import os
import re
from Cheetah.Template import Template

import common_utils
import lua_utils

_mInfo = {}
def _parseModuleInfo(className, fp: str):
    desc = [f'---@class {className}']
    lines = []
    for line in common_utils.read_utf8_file_lines(fp):
        mFunction = re.match(lua_utils.reGlobalFuncDeclare, line)
        if not mFunction:
            lines.append(line)
            continue

        _, arrParms, ret = lua_utils.parseFuncDesc(lines)
        funDesc = ['---@field ', mFunction.group(2), ' fun(']
        for i, (name, tp) in enumerate(arrParms):
            if i > 0:
                funDesc.append(', ')
            funDesc.append(f'{name}: {tp}')
        funDesc.append(f'): {ret}')
        lines.append(line)
        desc.append(''.join(funDesc))

    assert className not in _mInfo, className
    _mInfo[className] = {
        'desc': '\n'.join(desc),
        'path': fp.replace('.lua', '').replace('\\', '/'),
    } 

def _parse(fp: str):
    if os.path.isdir(fp):
        for i in os.listdir(fp):
            _parse(os.path.join(fp, i))
        return

    if not fp.endswith('.lua'):
        return
    
    with open(fp, 'r', encoding='utf-8') as f:
        s = f.read(100)
        if not s.startswith('---@declare_module_type'):
            return
        
        m = re.match(r'^---@declare_module_type\((.+)\)', s)
        if m:
            _parseModuleInfo(m.group(1), fp)


if __name__ == '__main__':
    with common_utils.pushd('../Content/src'):
        for d in os.listdir(os.getcwd()):
            _parse(d)

    outPutPath = os.path.abspath('../Content/src/lua_ext/module_manager.lua')
    common_utils.write_utf8_file_content(outPutPath, str(Template(file='config/module_manager.lua.tmpl', searchList=[{
        'mInfo': _mInfo,
    }])))
