#include "lua_module_register.h"

void registerCocosExtCFunction(lua_State* L);
void registerWinExtCFunction(lua_State* L);


int lua_module_register(lua_State* L) {
	registerCocosExtCFunction(L);
	registerWinExtCFunction(L);
	return 0;
}
