import re

import common_utils
import lua_utils


def formatLua(fPath):
    lines = []
    for line in common_utils.read_utf8_file_lines(fPath):
        if lua_utils.tryParseFunction(line, lines):
            pass
        elif lua_utils.tryParseGlobalVar(line, lines):
            pass

        lines.append(line)

    common_utils.write_utf8_file_content(fPath, ''.join(lines))


if __name__ == '__main__':
    
    fp = r'C:\projects\axmol\app\Content\src\test.lua'
    formatLua(fp)
