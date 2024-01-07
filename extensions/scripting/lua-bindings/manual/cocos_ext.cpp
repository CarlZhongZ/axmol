#include"cocos2d.h"
#include "scripting/lua-bindings/manual/Tolua.h"
#include "scripting/lua-bindings/auto/tolua_auto_convert.h"

#include <regex>
#include<iostream>

using namespace std;
using namespace ax;

////////////////////////////////////////////////////////////////////////////////////////
static int ccc3FromHex(lua_State *L) {
	int n = luaL_checkinteger(L, 1);
	GLubyte r = n >> 16 & 0xff;
	GLubyte g = n >> 8 & 0xff;
	GLubyte b = n & 0xff;
	tolua_push_value(L, Color3B(r, g, b));
	return 1;
}

static int ccc4FromHex(lua_State *L) {
	int n = luaL_checkinteger(L, 1);
	GLubyte r = n >> 16 & 0xff;
	GLubyte g = n >> 8 & 0xff;
	GLubyte b = n & 0xff;
	tolua_push_value(L, Color4B(r, g, b, 0xff));
	return 1;
}

//////////////////////////////////////////////////////
static Size s_winSize;
static float s_designWidth = 0.0f;
static float s_designHeight = 0.0f;
static float s_minRate = 1.0f;
static float s_maxRate = 1.0f;
static float s_xRate = 1.0f;
static float s_yRate = 1.0f;

static int ccext_update_design_resolution(lua_State *L) {
	s_winSize = Director::getInstance()->getWinSize();
	if (lua_gettop(L) != 4) {
		log("ccext_update_design_resolution params not valid");
		return 0;
	}
	if (lua_isnumber(L, 1)) {
		s_winSize.width = lua_tonumber(L, 1);
	}
	if (lua_isnumber(L, 2)) {
		s_winSize.height = lua_tonumber(L, 2);
	}
	s_designWidth = luaL_checknumber(L, 3);
	s_designHeight = luaL_checknumber(L, 4);
	s_minRate = MIN(s_winSize.width / s_designWidth, s_winSize.height / s_designHeight);
	s_maxRate = MAX(s_winSize.width / s_designWidth, s_winSize.height / s_designHeight);
	s_xRate = s_winSize.width / s_designWidth;
	s_yRate = s_winSize.height / s_designHeight;
	return 0;
}

static int ccext_get_designed_size(lua_State *L) {
	lua_pushnumber(L, s_designWidth);
	lua_pushnumber(L, s_designHeight);
	return 2;
}

static int ccext_get_scale(lua_State *L) {
	if (lua_isnumber(L, 1)) {
		lua_pushvalue(L, 1);
		return 1;
	}

	string s = luaL_checkstring(L, 1);
	if (s.empty()) {
		return 0;
	}

	char lats = s.back();
	s.pop_back();
	float v = atof(s.c_str());
	if (v > 0) {
		switch (lats) {
		case 'w':
		case 's':
			v *= s_minRate;
			break;
		case 'q':
			v *= s_maxRate;
			break;
		case 'k':
			v *= s_xRate;
			break;
		case 'g':
			v *= s_yRate;
			break;
		}
	}
	lua_pushnumber(L, v);
	return 1;
}


static regex pattern("([0-9.-]*)([%$]?)(i?)([0-9.-]*)");
static float _calc_pos(const string& pos, float parentLen, float selfScale) {
	cmatch cm;    // same as match_results<const char*> cm;
	if (!regex_match(pos.c_str(), cm, pattern)) {
		return 0;
	}

	string p1 = cm[1];
	string p2 = cm[2];
	string p3 = cm[3];
	string p4 = cm[4];

	float ret = 0;
	float offset = 0;

	if (p2 == "") {
		if (p3 == "i") {
			offset = parentLen - atof(p4.c_str());
		}
		else {
			offset = atof(p1.c_str());
		}
	}
	else {
		if (p2 == "%") {
			ret = parentLen * atof(p1.c_str()) / 100;
		}
		else if (p2 == "$") {
			ret = parentLen * atof(p1.c_str()) / (100 * selfScale);
		}

		if (p4 != "") {
			offset = atof(p4.c_str());
			if (p3 == "i") {
				offset = parentLen - offset;
			}
		}
	}

	return ret + offset;
}

static int ccext_calc_pos(lua_State *L)
{
	if (lua_isnumber(L, 1)) {
		lua_pushnumber(L, lua_tonumber(L, 1));
	}
	else {
		string pos = luaL_checkstring(L, 1);
		auto parentLen = luaL_checknumber(L, 2);
		lua_pushnumber(L, _calc_pos(pos, parentLen, lua_gettop(L) == 3?luaL_checknumber(L, 3):1.0f));
	}
	return 1;
}

static Node* _calcWH(lua_State *L, float& w, float& h) {
    auto cobj = (Node*)Tolua::toType(L, "cc.Node", 1);
    if (!cobj)
    {
        return 0;
    }

	if (lua_isnumber(L, 2)) {
		w = lua_tonumber(L, 2);
	}
	else {
		string sw = luaL_checkstring(L, 2);
		auto parent = cobj->getParent();
		if (parent) {
			w = _calc_pos(sw, parent->getContentSize().width, cobj->getScaleX());
		}
		else {
			w = _calc_pos(sw, s_winSize.width, cobj->getScaleX());
		}
	}

	if (lua_isnumber(L, 3)) {
		h = lua_tonumber(L, 3);
	}
	else {
		string sh = luaL_checkstring(L, 3);
		auto parent = cobj->getParent();
		if (parent) {
			h = _calc_pos(sh, parent->getContentSize().height, cobj->getScaleY());
		}
		else {
			h = _calc_pos(sh, s_winSize.height, cobj->getScaleY());
		}
	}
	return cobj;
}

static int ccext_node_calc_size(lua_State *L) {
	Size sz;
	_calcWH(L, sz.width, sz.height);
    Tolua::pushType(L, &sz, "cc.Vec2");
	return 1;
}

static int ccext_node_calc_pos(lua_State *L) {
	Vec2 p;
	_calcWH(L, p.x, p.y);
    Tolua::pushType(L, &p, "cc.Vec2");
	return 1;
}

static int ccext_node_set_content_size(lua_State *L) {
	Size sz;
	auto node = _calcWH(L, sz.width, sz.height);
	if (node) {
		node->setContentSize(sz);
        Tolua::pushType(L, &sz, "cc.Vec2");
		return 1;
	}
	else {
		return 0;
	}
}

static int ccext_node_set_position(lua_State *L) {
	Vec2 p;
	auto node = _calcWH(L, p.x, p.y);
	if (node) {
		node->setPosition(p);
        Tolua::pushType(L, &p, "cc.Vec2");
		return 1;
	}
	else {
		return 0;
	}
}

#if DEBUG_USE_CALC_REF_LEAK_DETECTION
static int ccext_debug_print_ref_leaks(lua_State *L) {
	lua_pushstring(L, Ref::printLeaks().c_str());
	return 1;
}

static int ccext_debug_set_ignore_ref_info(lua_State *L) {
    std::string key = luaL_checkstring(L, 1);
    int count = luaL_checkint(L, 2);
    Ref::addIgnoreInfo(key, count);
    return 0;
}

static int ccext_debug_ref_set_desc(lua_State *L) {
    auto ref = (Ref*)tolua_tousertype(L, 1, 0);
    std::string key = luaL_checkstring(L, 1);
    ref->setDescription(key);
    return 0;
}

#endif

void registerCocosExtCFunction(lua_State *L) {
	lua_register(L, "ccc3FromHex", ccc3FromHex);
	lua_register(L, "ccc4FromHex", ccc4FromHex);

	lua_register(L, "ccext_update_design_resolution", ccext_update_design_resolution);
	lua_register(L, "ccext_get_designed_size", ccext_get_designed_size);
	lua_register(L, "ccext_get_scale", ccext_get_scale);
	lua_register(L, "ccext_calc_pos", ccext_calc_pos);

	lua_register(L, "ccext_node_calc_size", ccext_node_calc_size);
	lua_register(L, "ccext_node_calc_pos", ccext_node_calc_pos);
	lua_register(L, "ccext_node_set_content_size", ccext_node_set_content_size);
	lua_register(L, "ccext_node_set_position", ccext_node_set_position);

#if DEBUG_USE_CALC_REF_LEAK_DETECTION
    lua_register(L, "ccext_debug_print_ref_leaks", ccext_debug_print_ref_leaks);
    lua_register(L, "ccext_debug_set_ignore_ref_info", ccext_debug_set_ignore_ref_info);
    lua_register(L, "ccext_debug_ref_set_desc", ccext_debug_ref_set_desc);
#endif
	
	//cocos2d::Director::getInstance()->setSizeChangeCallback([](float w, float h) {
	//	auto stack = LuaEngine::getInstance()->getLuaStack();
	//	auto top = lua_gettop(stack->getLuaState());
	//	stack->pushFloat(w);
	//	stack->pushFloat(h);
	//	stack->executeGlobalFunctionWithArgs("event_on_screen_size_changed", 2);
	//	lua_settop(stack->getLuaState(), top);
	//});
}
