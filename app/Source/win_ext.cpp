#if AX_TARGET_PLATFORM == AX_PLATFORM_WIN32
#include "cocos2d.h"
#include "base/Utils.h"
#include "platform/FileUtils.h"
#include "scripting/lua-bindings/manual/LuaEngine.h"
#include "scripting/lua-bindings/manual/Tolua.h"

#include <iostream>
#include <sstream>
#include <string>

#include <Windows.h>
//#include <locale>
#include <codecvt>
#include <commdlg.h>

static int winext_getSystemCopyBuffer(lua_State* L) {
    // �򿪼�����
    OpenClipboard(NULL);

    // ��ȡ���������ݾ��
    HANDLE hData = GetClipboardData(CF_TEXT);
    int ret = 0;
    if (hData != NULL)
    {
        // ��ȡ���ݾ��ָ����ڴ���ַ
        char* pszText = static_cast<char*>(GlobalLock(hData));

        if (pszText != NULL)
        {
            lua_pushstring(L, pszText);
            ++ret;

            // �ͷ���Դ
            GlobalUnlock(hData);
        }
    }

    // �رռ�����
    CloseClipboard();
    return ret;
}

static int winext_setSystemCopyBuffer(lua_State* L) {
    // �򿪼�����
    OpenClipboard(NULL);

    // ��ռ������е�����
    EmptyClipboard();

    size_t dataSize;
    const char* data = luaL_checklstring(L, 1, &dataSize);

    HGLOBAL hData = GlobalAlloc(GMEM_MOVEABLE, dataSize); // ����ȫ���ڴ�
    if (hData != NULL)
    {
        char* pszText = static_cast<char*>(GlobalLock(hData)); // ��ȡ�ڴ���ַ
        if (pszText != NULL)
        {
            memcpy(pszText, data, dataSize); // �����ݸ��Ƶ��ڴ��
            GlobalUnlock(hData);

            // �����ݾ�����õ�������
            SetClipboardData(CF_TEXT, hData);
        }
    }

    // �رռ�����
    CloseClipboard();
    return 0;
}

static std::wstring multibyteToWideChar(const std::string& utf8Str) {
    std::wstring_convert<std::codecvt_utf8_utf16<wchar_t>, wchar_t> convert;
    return convert.from_bytes(utf8Str);
}

static std::string wideCharToMultibyte(const std::wstring& utf16Str) {
    std::wstring_convert<std::codecvt_utf8_utf16<wchar_t>, wchar_t> convert;
    return convert.to_bytes(utf16Str);
}

static int winext_getFileLastWriteTime(lua_State* L) {
    auto path = multibyteToWideChar(luaL_checkstring(L, 1));

    HANDLE fileHandle = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (fileHandle == INVALID_HANDLE_VALUE) {
        return 0;
    }

    FILETIME ftCreate, ftAccess, ftWrite, ftLocal;
    SYSTEMTIME stUTC, stLocal;

    if (GetFileTime(fileHandle, &ftCreate, &ftAccess, &ftWrite)) {
        FileTimeToLocalFileTime(&ftWrite, &ftLocal);
        FileTimeToSystemTime(&ftLocal, &stLocal);

        std::ostringstream oss;
        oss << stLocal.wYear << "-" << stLocal.wMonth << "-" << stLocal.wDay << " "
            << stLocal.wHour << ":" << stLocal.wMinute << ":" << stLocal.wSecond << ":" << stLocal.wMilliseconds;
        lua_pushstring(L, oss.str().c_str());
        CloseHandle(fileHandle);
        return 1;
    }

    CloseHandle(fileHandle);
    return 0;
}

static int winext_getCommandLine(lua_State* L) {
    auto commandLine = GetCommandLine();
    lua_pushstring(L, wideCharToMultibyte(commandLine).c_str());
    return 1;
}

static int winext_getcwd(lua_State* L) {
    WCHAR buffer[MAX_PATH];
    GetCurrentDirectory(MAX_PATH, buffer);
    lua_pushstring(L, wideCharToMultibyte(buffer).c_str());
    return 1;
}

static int winext_setcwd(lua_State* L) {
    auto path = luaL_checkstring(L, 1);
    SetCurrentDirectory(multibyteToWideChar(path).c_str());
    return 0;
}

static int winext_getEnvVar(lua_State* L) {
    auto name = luaL_checkstring(L, 1);
    auto maxSize = 1024;
    auto buffer = new WCHAR[maxSize];
    while (true) {
        auto buffSize = GetEnvironmentVariable(multibyteToWideChar(name).c_str(), buffer, maxSize);
        if (buffSize == 0) {
            delete[]buffer;
            return 0;
        }
        else if (buffSize < maxSize) {
            buffer[buffSize] = 0;
            lua_pushstring(L, wideCharToMultibyte(buffer).c_str());
            delete[]buffer;
            return 1;
        }
        else {
            delete[]buffer;
            maxSize *= 2;
            buffer = new WCHAR[maxSize];
        }
    }

    return 0;
}

static int winext_setEnvVar(lua_State* L) {
    auto name = luaL_checkstring(L, 1);
    auto var = luaL_checkstring(L, 2);
    lua_pushboolean(L, SetEnvironmentVariable(multibyteToWideChar(name).c_str(), multibyteToWideChar(var).c_str()) != 0);
    return 1;
}

static int winext_runCommand(lua_State* L) {
    auto command = luaL_checkstring(L, 1);
    auto cwd = luaL_checkstring(L, 2);

    // �������̽ṹ��
    STARTUPINFO startupInfo;
    PROCESS_INFORMATION processInfo;
    ZeroMemory(&startupInfo, sizeof(startupInfo));
    ZeroMemory(&processInfo, sizeof(processInfo));
    startupInfo.cb = sizeof(startupInfo);
    startupInfo.dwFlags |= STARTF_USESTDHANDLES;  // ���ñ�׼��������ض���

    // �����ܵ������ض�����̵ı�׼���
    HANDLE hStdoutRead, hStdoutWrite;
    SECURITY_ATTRIBUTES saAttr;
    saAttr.nLength = sizeof(SECURITY_ATTRIBUTES);
    saAttr.bInheritHandle = TRUE;
    saAttr.lpSecurityDescriptor = NULL;
    if (!CreatePipe(&hStdoutRead, &hStdoutWrite, &saAttr, 0))
    {
        return 0;
    }

    // ���ý��̵ı�׼���Ϊ�ܵ���д���
    startupInfo.hStdOutput = hStdoutWrite;
    startupInfo.hStdError = hStdoutWrite;

    // ��������
    if (CreateProcess(NULL, (LPWSTR)multibyteToWideChar(command).c_str(), NULL, NULL, TRUE, 0, NULL, (LPWSTR)multibyteToWideChar(cwd).c_str(), &startupInfo, &processInfo))
    {
        // �ر����õĹܵ����
        CloseHandle(hStdoutWrite);

        // ��ȡ���̵ı�׼���
        const int BUFFER_SIZE = 4096;
        char buffer[BUFFER_SIZE];
        DWORD bytesRead;
        std::string output;

        while (ReadFile(hStdoutRead, buffer, BUFFER_SIZE - 1, &bytesRead, NULL) && bytesRead != 0)
        {
            output.append(buffer, bytesRead);
        }

        // �ȴ����̽���
        WaitForSingleObject(processInfo.hProcess, INFINITE);

        // �رս��̺��߳̾��
        CloseHandle(processInfo.hProcess);
        CloseHandle(processInfo.hThread);
        CloseHandle(hStdoutRead);

        lua_pushlstring(L, output.c_str(), output.length());
        return 1;
    }
    else
    {
        return 0;
    }
}


void registerWinExtCFunction(lua_State* L) {
    lua_register(L, "winext_getSystemCopyBuffer", winext_getSystemCopyBuffer);
    lua_register(L, "winext_setSystemCopyBuffer", winext_setSystemCopyBuffer);
    lua_register(L, "winext_getFileLastWriteTime", winext_getFileLastWriteTime);
    lua_register(L, "winext_getCommandLine", winext_getCommandLine);
    lua_register(L, "winext_getcwd", winext_getcwd);
    lua_register(L, "winext_setcwd", winext_setcwd);
    lua_register(L, "winext_getEnvVar", winext_getEnvVar);
    lua_register(L, "winext_setEnvVar", winext_setEnvVar);
    lua_register(L, "winext_runCommand", winext_runCommand);
}
#else
void registerWinExtCFunction(lua_State* L) {
}
#endif
