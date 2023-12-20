        if self.parents:
            parent = self.parents[0]
            self.generator.declare_lua_file.write('\n\n---@class %s: %s' % (self.lua_class_name, parent.lua_class_name))
        else:
            self.generator.declare_lua_file.write('\n\n---@class %s' % (self.lua_class_name))
    
def _genLuaClassDesc(self, gen):
        gen.declare_lua_file.write('\n---@field %s fun(' % self.func_name)
        for i in range(self.min_args):
            argName = self.argumtntTips[i]
            argType = self.arguments[i].luaType
            if i > 0:
                gen.declare_lua_file.write(', ')
            gen.declare_lua_file.write('%s: %s' % (argName, argType))

        for i in range(self.min_args, len(self.arguments)):
            argName = self.argumtntTips[i]
            argType = self.arguments[i].luaType
            if i > 0:
                gen.declare_lua_file.write(', ')
            gen.declare_lua_file.write('%s?: %s' % (argName, argType))
        gen.declare_lua_file.write('): ')
        gen.declare_lua_file.write(self.ret_type.luaType)


declareLuaClassFilePath = os.path.join(self.outdir, self.out_file + ".lua")
self.declare_lua_file = open(declareLuaClassFilePath, "wt+", encoding='utf8', newline='\n')