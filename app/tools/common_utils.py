# -*- coding:utf-8 -*-
import os
import shutil
import re
import hashlib
import sys
import json
from contextlib import contextmanager
from PIL import Image
import socket
import uuid
import traceback
import requests
import gzip
import subprocess
import zipfile
from importlib import import_module
from io import StringIO

import ssl
context = ssl._create_unverified_context()

# 获得指定文件所在的目录全路径 默认为 common_utils 目录
def get_cur_file_dir(file=None):
    if file is None:
        if os.path.isfile(__file__):
            file = __file__
        else:
            return os.getcwd()

    assert os.path.isfile(file)
    curDir = os.path.dirname(file)
    return os.path.abspath(curDir)

config_tool_path = os.path.join(get_cur_file_dir(), 'external_tools')
assert os.path.isdir(config_tool_path)

def get_valid_file_name(fileName):
    return re.sub(r'[:?,\\/*"<>| ]+', '', fileName)

@contextmanager
def sys_path_push_pre_file_folder(filePath):
    assert os.path.isfile(filePath)
    preDir = os.path.abspath(os.path.join(os.path.dirname(filePath), '..'))
    sys.path.append(preDir)
    yield
    sys.path.pop()

@contextmanager
def sys_path_push_folder(d):
    assert os.path.isdir(d)
    sys.path.append(d)
    yield
    sys.path.pop()

@contextmanager
def pushd(newDir):
    assert os.path.isdir(newDir)

    previousDir = os.getcwd()
    os.chdir(newDir)
    yield
    os.chdir(previousDir)

@contextmanager
def change_std_out(newFobj):
    old_std_out = sys.stdout
    sys.stdout = newFobj
    yield
    sys.stdout = old_std_out

@contextmanager
def create_new_dir_and_later_remove(newDir, bChangeCurDir):
    assert not os.path.exists(newDir), newDir
    create_dir_if_not_exists(newDir)

    if bChangeCurDir:
        previousDir = os.getcwd()
        os.chdir(newDir)
        yield
        os.chdir(previousDir)
    else:
        yield
    shutil.rmtree(newDir)

def os_is_mac():
    return sys.platform == 'darwin'

def os_is_linux():
    return 'linux' in sys.platform

def os_is_win32():
    return sys.platform == 'win32'

_tempFileIndex = 0
def get_temp_file_name():
    global _tempFileIndex
    _tempFileIndex += 1
    tempFolder = os.path.join(get_cur_file_dir(), 'temp_folder')
    create_dir_if_not_exists(tempFolder)
    return os.path.join(tempFolder, 'temp_file_%d' % _tempFileIndex)

#获取文件 md5 码
def get_file_md5(filePath):
    hashobj = hashlib.md5()
    with open(filePath, 'rb') as f:
        hashobj.update(f.read())
    md5_str = hashobj.hexdigest()
    return md5_str

def get_str_md5(s):
    hashobj = hashlib.md5()
    hashobj.update(s)
    md5_str = hashobj.hexdigest()
    return md5_str

def Print(s):
    try:
        print(s)
    except Exception as e:
        pass
    else:
        pass
    finally:
        pass

def Notice(s):
    print('\n\n')
    Print(s)
    print('\n\n')
    Print('按任意键继续')
    input()

def Warning(s):
    print('\n\n')
    Print(s)
    print('\n\n')
    Print('输入 yes 继续')
    result = input()
    if result != 'yes':
        raise Exception('warning not enter yes')

def Allert(msg):
    print('\n\n\n\n\n----------------------------------------------------------------')
    print(msg)
    print('----------------------------------------------------------------\n\n\n\n\n')

Alert = Allert

def get_user_input(msg):
    print(msg)
    return input()

s_cipher_key = ''
def SetCipherKey(key):
    assert key and isinstance(key, str)
    s_cipher_key = key

def CipherFile(sourceF, destFilePath, bCompressed=False):
    # print('cipher file:', sourceF, destFilePath)
    if bCompressed:
        tempFile = get_temp_file_name()
        if zip_compress_file_if_little(sourceF, tempFile):
            sourceF = tempFile

    if s_cipher_key:
        if os_is_win32():
            cmd = '%s %s %s %s' % (os.path.join(config_tool_path, 'cipher.exe'), sourceF, destFilePath, s_cipher_key)
    else:
        if os_is_win32():
            cmd = '%s %s %s' % (os.path.join(config_tool_path, 'cipher.exe'), sourceF, destFilePath)
        elif os_is_mac():
            cmd = '%s %s %s' % (os.path.join(config_tool_path, 'cipher-mac'), sourceF, destFilePath)

    os.system(cmd)

    if bCompressed:
        remove_file_if_exists(tempFile)

def compile_lua(src, dest):
    # print('compile lua: ', src, dest)
    # cmd = os.path.join(config_tool_path, 'luac.exe')  + ' -o ' + dest + ' ' + src
    # cmd = os.path.join(config_tool_path, 'luajit.exe')  + ' -b ' + src + ' ' + dest

    remove_file_if_exists(dest)
    luajitPath = os.path.join(config_tool_path, 'luajit', os_is_mac() and '64bit' or '32bit')
    assert(os.path.isdir(luajitPath))

    if os_is_win32():
        cmd = '%s -b %s %s' % ('luajit-win32.exe', src, dest)
    elif os_is_mac():
        cmd = '%s -b %s %s' % ('./luajit-mac', src, dest)
    # with pushd(luajitPath):
    # os.system(cmd)
    exec_cmd(cmd, luajitPath)
    return os.path.isfile(dest)

def CompileScript(src, dest, bCompile=False, bCompressed=False):
    if bCompressed:
        assert not bCompile

    if bCompile:
        compile_lua(src, dest)
        CipherFile(dest, dest)
    else:
        # 编译检测语法有效性
        fname = get_temp_file_name()
        if compile_lua(src, fname):
            os.remove(fname)
        else:
            print('\n\ncompile lua [%s] failed!!!!!!!!!!!!!\n\n' % src)
        CipherFile(src, dest, bCompressed)

def gzip_compress(raw_data):
    buf = StringIO()
    f = gzip.GzipFile(mode='wb', fileobj=buf, compresslevel=9)
    try:
        f.write(raw_data)
    finally:
        f.close()
    return buf.getvalue()

def gzip_uncompress(c_data):
    buf = StringIO(c_data)
    f = gzip.GzipFile(mode = 'rb', fileobj = buf)
    try:
        r_data = f.read()
    finally:
        f.close()
    return r_data

def gzip_compress_file(srcPath, destPath):
    assert os.path.isfile(srcPath)

    with open(srcPath, 'rb') as f:
        raw_data = f.read()

    with open(destPath, 'wb') as f:
        f.write(gzip_compress(raw_data))

    assert os.path.isfile(destPath)

def gzip_uncompress_file(srcPath, destPath):
    assert os.path.isfile(srcPath)

    with open(srcPath, 'rb') as f:
        c_data = f.read()

    with open(destPath ,'wb') as f:
        f.write(gzip_uncompress(c_data))

    assert os.path.isfile(destPath)

def gzip_compress_file_if_little(srcPath, destPath):
    tempF = get_temp_file_name()
    gzip_compress_file(srcPath, tempF)
    lessSize = os.path.getsize(srcPath) - os.path.getsize(tempF)
    if lessSize <= 0:
        os.remove(tempF)
        return False
    else:
        print('gzipFile[%s] less:%d' % (srcPath, lessSize))
        shutil.move(tempF, destPath)
        return True

# from zipfile import  PyZipFile
def _getAllFilePathsInDir(inputPath, result):
    files = os.listdir(inputPath)
    for file in files:
        if os.path.isdir(inputPath + '/' + file):
            _getAllFilePathsInDir(inputPath + '/' + file, result)
        else:
            result.append(inputPath + '/' + file)
 
def zip_file_path(inputPath, outputPath):
    outputPath = os.path.abspath(outputPath)
    d, fileName = os.path.split(inputPath)
    with pushd(d):
        f = zipfile.ZipFile(outputPath, 'w', zipfile.ZIP_DEFLATED)
        if os.path.isfile(fileName):
            filelists = [fileName]
        elif os.path.isdir(fileName):
            filelists = []
            _getAllFilePathsInDir(fileName, filelists)
        for file in filelists:
            f.write(file)
        f.close()

# 1.由于用extractall遇到中文有机会乱码
# 2.整体思路是：一个一个提取，并用正确文件名命名。
def extract_file(zip_path,out_path):
    '''
    解压缩文件到指定目录
    '''
    import os
    path=out_path
    zfile=zipfile.ZipFile(zip_path)
    for f in zfile.namelist():
        # 防止中文乱码
        try:
            f1=f.encode('cp437').decode('gbk')
        except Exception as e:
            f1=f.encode('utf-8').decode('utf-8')
        zfile.extract(f,path)
        os.chdir(path)  #切换到目标目录
        os.rename(f,f1)

def match(strList, name):
    for i in strList:
        if re.search(i, name):
            return True

# 将文件夹复制到制定目录下
def copytree(src, dst, filterList=None, ignorList=None, bOnlyFiles=False):
    def _copy(src, dst):
        # print('copytree', src, dst)
        if not os.path.exists(dst):
            os.makedirs(dst)

        for name in os.listdir(src):
            if filterList is not None:
                if not match(filterList, name):
                    continue
            if ignorList is not None:
                if match(ignorList, name):
                    continue

            srcname = os.path.join(src, name)
            dstname = os.path.join(dst, name)
            if os.path.isdir(srcname):
                if bOnlyFiles:
                    continue
                _copy(srcname, dstname)
            elif os.path.isfile(srcname):
                shutil.copy(srcname, dstname)

    _copy(src, dst)

def copy_file_and_create_dir_if_not_exists(srcBasePath, destBasePath, srcPath):
    srcPath = srcPath.replace('\\', '/')
    srcFilePath = os.path.join(srcBasePath, srcPath)
    assert os.path.isfile(srcFilePath), srcFilePath
    assert os.path.isdir(destBasePath), destBasePath

    listName = srcPath.split('/')
    for i, fname in enumerate(listName):
        destBasePath = os.path.join(destBasePath, fname)
        if i == len(listName) - 1:
            shutil.copyfile(srcFilePath, destBasePath)
            return srcFilePath, destBasePath
        else:
            create_dir_if_not_exists(destBasePath)

def copy_full_path_file(srcFilePath, destFilePath):
    assert os.path.isfile(srcFilePath)
    create_dir_if_not_exists(os.path.dirname(destFilePath))
    shutil.copyfile(srcFilePath, destFilePath)

def move_file_and_create_dir_if_not_exists(srcBasePath, destBasePath, srcPath):
    copy_file_and_create_dir_if_not_exists(srcBasePath, destBasePath, srcPath)
    os.remove(os.path.join(srcBasePath, srcPath))

def sync_dir(srcDir, destDir, callback=None):
    assert os.path.isdir(srcDir)
    create_dir_if_not_exists(destDir)

    for f in os.listdir(srcDir):
        fPath = os.path.join(srcDir, f)
        fDestPath = os.path.join(destDir, f)

        if os.path.isfile(fPath):
            assert not os.path.isdir(fDestPath)
            shutil.copyfile(fPath, fDestPath)
            if callback:
                callback(fPath, fDestPath)
        elif os.path.isdir(fPath):
            create_dir_if_not_exists(fDestPath)
            sync_dir(fPath, fDestPath)

def remove_dir_if_exists(d):
    if os.path.isdir(d):
        try:
            shutil.rmtree(d)
        except Exception as e:
            if os_is_win32():
                raise Exception('remove folder [%s] failed' % d)
            elif os_is_mac():
                print('use sudo rm -rf %s' % d)
                os.system('sudo rm -rf %s' % d)

        assert not os.path.isdir(d)

def empty_dir(d):
    remove_dir_if_exists(d)
    create_dir_if_not_exists(d)

def remove_file_if_exists(f):
    if os.path.isfile(f):
        os.remove(f)

def create_dir_if_not_exists(d):
    def _mkdir(dd):
        if os.path.isdir(dd):
            return True
        else:
            d1, d2 = os.path.split(dd)
            if d1 and d2:
                _mkdir(d1)
                os.makedirs(dd)
            else:
                raise Exception('dir error')

    try:
        _mkdir(os.path.abspath(d))
        assert os.path.isdir(d)
    except Exception as e:
        print(e)
        raise Exception('create_dir_if_not_exists [%s] failed' % str(d))

def clear_dir(d):
    assert os.path.isdir(d)
    shutil.rmtree(d)
    os.makedirs(d)

def copy_file_to_base_relative_path(filePath, destBasePath, destRelativePath):
    assert os.path.isfile(filePath)
    assert os.path.isdir(destBasePath)
    listPath = []
    curPath, fileName = os.path.split(destRelativePath)
    while curPath:
        curPath, n = os.path.split(curPath)
        listPath.insert(0, n)

    for d in listPath:
        destBasePath = os.path.join(destBasePath, d)
        create_dir_if_not_exists(destBasePath)

    destFilePath = os.path.join(destBasePath, fileName)
    shutil.copyfile(filePath, destFilePath)
    assert os.path.isfile(destFilePath)
    return destFilePath


def get_ip_address():
    """
    查询本机ip地址
    :return: ip
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    return ip

def get_mac_address():
    mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    return ":".join([mac[e:e+2] for e in range(0,11,2)])

def is_png_format(filePath):
    ret = False
    try:
        img = Image.open(filePath)
        ret = img.format == 'PNG'
        # with  as :
        #     print(img.format)
    except Exception as e:
        # print(e)
        pass
    else:
        pass
    finally:
        pass

    return ret

def trans_2_png8(sourceF, destFilePath):
    # print('convert [%s] to png8 [%s]' % (sourceF, destFilePath))
    if os_is_win32():
        trans_png8_path = os.path.join(config_tool_path, 'trans_png8', 'pngquant.exe')
    elif os_is_mac():
        trans_png8_path = os.path.join(config_tool_path, 'trans_png8', 'pngquant', 'pngquant')

    cmd = '%s --force -o %s 256 %s' % (trans_png8_path, destFilePath, sourceF)
    cmdRet = execCmd(cmd)
    if cmdRet.find('libpng failed') != -1:
        print(cmdRet, 'use origin png')
        shutil.copyfile(sourceF, destFilePath)

    # ptrTextToolPath = os.path.join('pvr_tex_tool', 'PVRTexToolCLI.exe')
    # pvrPath = destFilePath+'.pvr'
    # cmd = '%s -f PVRTC2_4 -q pvrtcfast -legacypvr -l -i %s -o %s' % (ptrTextToolPath, sourceF, pvrPath)
    # # print('convert png to pvrtc')
    # # print(cmd)
    # os.system(cmd)
    # CipherFile(pvrPath, destFilePath)
    # if os.path.isfile(pvrPath):
    #     os.remove(pvrPath)
    # else:
    #     print('error: [%s] convert pvrtc failed' % sourceF)

def pcall(fun, *args):
    try:
        return fun(*args)
    except Exception as e:
        print(e)
        traceback.print_exc()
    else:
        pass
    finally:
        pass

def svn_checkout_or_update(folderPath, svnPath):
    if os.path.isdir(folderPath):
        cmd = 'svn up'
        with pushd(folderPath):
            os.system(cmd)
    else:
        cmd = 'svn checkout %s %s' % (svnPath, folderPath)
        os.system(cmd)

def svn_get_svn_path(folderPath):
    if os.path.isdir(folderPath):
        with pushd(folderPath):
            listoutput = execCmd('svn info').split('\n')
            print(listoutput)
            for line in listoutput:
                m = re.match('^URL: (.+)$', line)
                if m:
                    return m.group(1)
                    break

def svn_force_revert_or_checkout_update(folderPath, svnPath):
    if svn_get_svn_path(folderPath) == svnPath:
        svn_revert_and_update(folderPath)
    else:
        remove_dir_if_exists(folderPath)
        svn_checkout_or_update(folderPath, svnPath)

def svn_revert_and_update(folderPath):
    assert os.path.isdir(folderPath)

    with pushd(folderPath):
        for line in execCmd('svn status').split('\n'):
            # print(line)
            if line.startswith('M') or line.startswith('!') or line.startswith('D'):
                name = line[8:]
                exec_cmd('svn revert %s' % name)
            elif line.startswith('A'):
                name = line[8:]
                assert os.path.isfile(name)
                exec_cmd('svn revert %s' % name)
                os.remove(name)
            elif line.startswith('?'):
                name = line[8:]
                if os.path.isfile(name):
                    os.remove(name)
                elif os.path.isdir(name):
                    shutil.rmtree(name)
                else:
                    raise Exception('svn_revert_and_update failed!:%s' % name)
                

        exec_cmd('svn up')
        assert execCmd('svn status') == ''

def svn_status(folderPath):
    ret = []
    assert os.path.isdir(folderPath)

    svnSymbos = set(['M', '!', 'D', 'A', '?'])
    with pushd(folderPath):
        if execCmd('svn status') == '':
            return

        for line in execCmd('svn status').split('\n'):
            if not line:
                continue

            firstCh = line[0:1]
            if firstCh in svnSymbos:
                name = line[8:]
                ret.append([firstCh, name])
            else:
                continue

            # check
            if firstCh == '!' or firstCh == 'D':
                assert not os.path.isfile(name)
            elif firstCh == 'A' or firstCh == 'M' or firstCh == '?':
                assert os.path.isfile(name) or os.path.isdir(name)

    return ret

config_svn_ci_glags = ('M', '?', '!', 'A', 'D', '~')
def svn_ci(folderPath, flags, comment):
    assert os.path.isdir(folderPath)
    assert comment.find('"') == -1, 'comment [%s] not valid' % comment
    assert comment.find("'") == -1, 'comment [%s] not valid' % comment
    if isinstance(flags, str):
        flags = [flags, ]
    elif flags is None:
        flags = config_svn_ci_glags

    for flag in flags:
        assert flag in config_svn_ci_glags

    with pushd(folderPath):
        # os.system('svn up')
        listChanged = []
        for line in execCmd('svn status').split('\n'):
            # print(line)
            if len(line) == 0:
                continue

            flag = line[0]
            if flag in flags:
                name = line[8:]
                if os.path.isfile(name):
                    listChanged.append(name)
                    if flag == '?':
                        os.system('svn add %s' % name)
                elif flag == '!':
                    listChanged.append(name)
                    os.system('svn delete %s' % name)
                elif flag == '~':
                    listChanged.append(name)
                    os.system('svn revert %s' % name)
                    os.system('svn delete %s' % name)

        if listChanged:
            cmd = 'svn ci %s -m"%s"' % (' '.join(listChanged), comment)
            print(cmd)
            os.system(cmd)


# On branch master
# [Your branch is up to date with] / [Your branch is behind]
# Changes to be committed:
# Changes not staged for commit:
# Untracked files:
def git_check_folder(folderPath):
    assert os.path.isdir(folderPath), 'folder [%s] not exists' % folderPath
    # assert os.path.isdir(os.path.join(folderPath, '.git'))

    with pushd(folderPath):
        listoutput = execCmd('git status').split('\n')

        m = re.match(r'^On branch (.+)$', listoutput[0])
        if m:
            curBranchName = m.group(1)
        else:
            assert listoutput[0].startswith('HEAD detached at '), listoutput[0]
            curBranchName = listoutput[0]

        listModified = []
        listUntracked = []
        listDeleted = []
        bCheckNotStagedForCommit = False
        bCheckUntrackedFiles = False
        def _parseStr(s):
            return s.startswith('"') and eval(s) or s

        for line in listoutput:
            # print(line, line == 'Untracked files:')
            assert line != 'Changes to be committed:', line

            if line == 'Changes not staged for commit:':
                bCheckNotStagedForCommit = True
            elif line == 'Untracked files:':
                bCheckUntrackedFiles = True
            elif bCheckUntrackedFiles:
                m = re.match(r'^\t(.+)$', line)
                if m:
                    listUntracked.append(_parseStr(m.group(1)))
            elif bCheckNotStagedForCommit:
                mModified = re.match(r'^[\t ]*modified:   (.+)$', line)
                if mModified:
                    listModified.append(_parseStr(mModified.group(1)))
                else:
                    mDeleted = re.match(r'^[\t ]*deleted:    (.+)$', line)
                    if mDeleted:
                        listDeleted.append(_parseStr(mDeleted.group(1)))


        if listModified or listDeleted or listUntracked:
            for fname in listModified:
                assert os.path.isfile(fname), '[%s] should exists' % fname

            for fname in listDeleted:
                assert not os.path.isfile(fname), '[%s] should not exists' % fname

            listUntrackedFiles = []
            for fname in listUntracked:
                if os.path.isfile(fname):
                    listUntrackedFiles.append(fname)
                else:
                    assert os.path.isdir(fname), 'dir [%s] not exists' % fname
            listUntracked = listUntrackedFiles

        listModified.extend(listDeleted)
        return curBranchName, listModified, listUntracked

def git_get_all_branches(folderPath):
    curBranchName = git_check_folder(folderPath)[0]

    with pushd(folderPath):
        listoutput = execCmd('git branch')
        if curBranchName.startswith('HEAD detached at '):
            ret = []
        else:
            ret = [curBranchName]

    for line in listoutput.split('\n'):
        if not line:
            continue

        if line[0] == '*':
            pass
        elif line.startswith('  '):
            ret.append(line[2:])

    return ret

def git_get_all_remote_origin_branches(folderPath):
    curBranchName = git_check_folder(folderPath)[0]

    with pushd(folderPath):
        listoutput = execCmd('git branch -a')
        ret = []

    for line in listoutput.split('\n'):
        if not line:
            continue

        m = re.match(r'^  remotes/origin/(.+$)', line)
        if m:
            branchName = m.group(1)
            if not branchName.startswith('HEAD'):
                ret.append(branchName)

    return ret

# 同步到指定gitPath分之，更改的文件全部恢复
def git_force_clone_or_checkout_pull(folderPath, gitPath, branchName):
    if not os.path.isdir(folderPath):
        os.system('git clone -b master %s %s' % (gitPath, folderPath))
    elif gitPath and git_remote_get_url(folderPath) != gitPath:
        git_remote_set_url(folderPath, gitPath)

    bCheckoutBranch = branchName in git_get_all_remote_origin_branches(folderPath)

    exec_cmd('git reset HEAD --hard', folderPath)
    _, _, listUntracked = git_check_folder(folderPath)
    with pushd(folderPath):
        # remove untracked files
        for fname in listUntracked:
            print('remove untracked files or folder', fname)
            if os.path.isfile(fname):
                os.remove(fname)
            else:
                shutil.rmtree(fname)

        if bCheckoutBranch:
            # exec_cmd('git pull --rebase')
            exec_cmd('git checkout %s' % branchName)
            exec_cmd('git pull --rebase')
        else:
            # checkout 2 commit id or tag
            exec_cmd('git checkout master')
            exec_cmd('git pull --rebase')
            exec_cmd('git checkout %s' % branchName)

        # validate
        curBranchName, listModified, listUntracked = git_check_folder(folderPath)
        assert not listModified, str(listModified)
        assert not listUntracked, str(listUntracked)
        if bCheckoutBranch:
            assert curBranchName == branchName
        else:
            m = re.match(r'^HEAD detached at (.+)$', curBranchName)
            assert m, curBranchName
            assert branchName.startswith(m.group(1)), m.group(1)

        exec_cmd('git status')

def git_force_merge(folderPath, gitPath, srcBranch, destBranch):
    git_force_clone_or_checkout_pull(folderPath, gitPath, srcBranch)
    git_force_clone_or_checkout_pull(folderPath, gitPath, destBranch)

    with pushd(folderPath):
        os.system('git merge -v %s' % srcBranch)

def git_ci_push(folderPath):
    # git ci
    with pushd(folderPath):
        print('ci info')

        curBranchName, listModified, listUntracked = git_check_folder(folderPath)
        for fname in listModified:
            if fname.find("build_atlas_info") >= 0:
                continue
            assert not fname.startswith('..'), '[%s] have invalid modified file:%s' % (folderPath, fname)

            if os.path.isfile(fname):
                exec_cmd('git add %s' % fname)
            else:
                exec_cmd('git rm %s' % fname)

        for fname in listUntracked:
            assert not fname.startswith('..'), '[%s] have invalid untracked file:%s' % (folderPath, fname)
            exec_cmd('git add %s' % fname)

        if listModified or listUntracked:
            exec_cmd('git commit . -m"%s"' % 'program auto commit config')
            exec_cmd('git push --progress origin %s' % curBranchName)
        else:
            print('unchanged no need to commit and push')

def git_remote_get_url(path, name='origin'):
    with pushd(path):
        listOut = execCmd('git remote -v').split('\n')
        try:
            urlFetch = listOut[0].split(' ')[0].split('\t')[1]
            urlPush = listOut[1].split(' ')[0].split('\t')[1]
            # print(urlFetch, urlPush)
            assert urlFetch == urlPush
            return urlPush            
        except Exception as e:
            print(str(listOut))
            raise e

def git_remote_set_url(path, url, name='origin'):
    cmd = 'git remote set-url %s %s' % (name, url)
    exec_cmd(cmd, path)

def get_url_content(url):
    tryCount = 0
    r = None
    while not r:
        try:
            r = requests.get(url, timeout=60)
        except Exception as e:
            tryCount += 1
            if tryCount >= 6:
                raise Exception('get_url_content [%s] reached max tryCount' % url)
            print('visit page url failed retry', url)

    return r.content

def download_big_file(url, targetFilePath):
    try:
        remove_file_if_exists(targetFilePath)
        with open(targetFilePath, 'wb') as f:
            f.write(get_url_content(url))
    except Exception as e:
        print(e)
        print('retry download_big_file', url)
        download_big_file(url, targetFilePath)

def url_download_file(urlPath, nativePath, md5=None, size=None, relativePath=None):
    print('url_download_file', urlPath, nativePath)

    remove_file_if_exists(nativePath)

    def _doDownload():
        download_big_file(urlPath, nativePath)
        # with open(nativePath, "wb") as code:
        #      code.write(get_url_content(urlPath))

    if md5 and size and relativePath:
        config_download_folder = os.path.join(get_cur_file_dir(), 'temp_download_folder')
        create_dir_if_not_exists(config_download_folder)
        fp = os.path.join(config_download_folder, relativePath)
        if os.path.isfile(fp) and get_file_md5(fp) == md5 and os.path.getsize(fp) == size:
            print('use native file', fp)
            shutil.copyfile(fp, nativePath)
        else:
            _doDownload()
            curDir = config_download_folder
            listDirName = relativePath.split('/')
            for i, dirName in enumerate(listDirName):
                curDir = os.path.join(curDir, dirName)
                if i == len(listDirName) - 1:
                    shutil.copyfile(nativePath, fp)
                else:
                    create_dir_if_not_exists(curDir)
    else:
        _doDownload()

    assert os.path.isfile(nativePath)

    if md5 and size:
        downloadMD5, downloadSize = get_file_md5(nativePath), os.path.getsize(nativePath)

        if downloadMD5 != md5 or downloadSize != size:
            print('!!!!!!!!!!download [%s] md5[%s] size[%d] not equal 2 md5[%s] size[%d]' % (urlPath, downloadMD5, downloadSize, md5, size))

def url_get_download_file_json(urlPath):
    try:
        return json.loads(get_url_content(urlPath))
    except Exception as e:
        print('url_get_download_file_json [%s] not a valid json format' % urlPath)
        return None

# execute command, and return the output
def execCmd(cmd):
    cmd = cmd.split(' ')
    # cmd = string.split()
    # print(cmd)

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (result, error) = p.communicate()
    # retcode = p.returncode

    # print(result, error)
    try:
        return result.decode('utf-8')
    except:
        return result

def exec_cmd(cmd, cwd=None):
    if cwd is None:
        cwd = os.getcwd()

    print('\nexec_cmd pwd[%s]:\n%s\n' % (cwd, cmd))

    return subprocess.call(cmd, shell=True, cwd=cwd)

def zip_compress_file(srcPath, destPath):
    if os.path.isdir(srcPath):
        cmd = 'zip -q -r -9 %s %s' % (destPath, srcPath)
        os.system(cmd)
    elif os.path.isfile(srcPath):
        srcPath = srcPath.replace('\\', '/')
        path, fileName = os.path.split(srcPath)
        ft = get_temp_file_name() + '.zip'
        if path:
            print(path)
            cmd = 'zip -q -9 %s %s' % (ft, fileName)
            print(cmd)
            exec_cmd(cmd, path)
            # with pushd(path):
            #     cmd = 'zip -q -9 %s %s' % (ft, fileName)
            #     print(cmd)
            #     os.system(cmd)
        else:
            cmd = 'zip -q -9 %s %s' % (ft, fileName)
            print(cmd)
            os.system(cmd)

        assert os.path.isfile(ft)
        shutil.move(ft, destPath)
    else:
        raise

    assert os.path.isfile(destPath)

def zip_compress_file_if_little(srcPath, destPath):
    assert os.path.isfile(srcPath)
    tempF = get_temp_file_name()
    zip_compress_file(srcPath, tempF)
    lessSize = os.path.getsize(srcPath) - os.path.getsize(tempF)
    if lessSize <= 0:
        os.remove(tempF)
        return False
    else:
        print('zipFile[%s] less:%d' % (srcPath, lessSize))
        shutil.move(tempF, destPath)
        return True

def compress_folder(folderPath, zipFilePath):
    assert os.path.isdir(folderPath)
    remove_file_if_exists(zipFilePath)
    cmd = 'zip -q -r -9 %s %s' % (zipFilePath, folderPath)
    # print(cmd)
    os.system(cmd)
    assert os.path.isfile(zipFilePath), zipFilePath

def uncompress_to_folder(zipFilePath, outDir):
    assert os.path.isfile(zipFilePath)
    # assert not os.path.isdir(outDir)

    cmd = 'unzip -q %s -d %s' % (zipFilePath, outDir)
    # print(cmd)
    os.system(cmd)
    assert os.path.isdir(outDir)

def print_json_format(v):
    print(json.dumps(v, indent = 4, sort_keys = True))

def print_dic_diff(dic1, dic2):
    listContent = ['diff begin----------------\n']

    def _print(*args):
        listContent.extend(args)

    def _printIndent(indent):
        for i in range(indent):
            listContent.append('\t')
        
    def _printDiff(dic1, dic2, indent):
        assert isinstance(dic1, dict)
        assert isinstance(dic2, dict)
        for k, v2 in dic2.items():
            if k not in dic1:
                _printIndent(indent)
                _print(k, ' add\n')
            else:
                v1 = dic1[k]
                if v2 != v1:
                    _printIndent(indent)
                    
                    if isinstance(v2, dict) and isinstance(v1, dict):
                        _print(k, ' changed    :\n')
                        _printDiff(v1, v2, indent + 1)
                    else:
                        _print(k, ' changed    :')
                        _print(str(v1), '    --->    ', str(v2), '\n')

        for k, v1 in dic1.items():
            if k not in dic2:
                _printIndent(indent)
                _print(k, ' del\n')

    _printDiff(dic1, dic2, 0)

    listContent.append('diff end----------------\n')
    print(''.join(listContent))

def save_dict_to_json_file(dic, filePath):
    assert isinstance(dic, dict)
    content = json.dumps(dic, indent = 4, sort_keys = True)
    write_utf8_file_content(filePath, content)
    return content

cipherKey = bytearray("hewTfHDvrKHg5fBQoQ0ucrieJZc0dI8H1XqaOhVNfpW0roVUfbNKw2Xr1k4N7lyptCIqwTzVaqZ08yibCCcVU1SvmN41RX8225x9KlDyQ12A2ZWXATJVVtTK4gpRbtq05r0BOVqbOf86bycrFbYRvNnV8kOjvpscEj4Jx8GGul54l3qgQ71pA9w3abVkJNiLJn5FnCWBBbCzaCETuo9K3Q7ERGQZg0x8Y7HpSsAbAkSYaqVAFtYz2h4aQ3k0Gzpstab6fomEtIZcvmtX9DbPoI4vhMdiXyNRPjzWQ0aI2NYGE3K4Pi5HzQ9EIgkIe4TfYXY30tlAtkrZdXfuJSfitiuFTuGoten4LTHyNFGvljLVEcpXEwoN0BWbeNq7UDo3VmIXQGsZRM60gTrG7ur5XOIeM4svRKHhH56MvuaIZn6UFNuAVVbJnhiu7fbw39d8hyxeYKEiNaEE6RjXRMqvnCsYq0rUbcDtv1hCtjR6SxuU0EDHLbJCS0d8xd9nTIX0zlnqOw9Rin3Qy1vX3G6kZiKR4fIgI6alvwXcuhDnYZWTkVMaUQ37A3ikTOh3hjybpR1ECwbg7UTKMJepHoo7xyoRk6U2Cyt6yY9dMNLEVQx3tHctVPeJv0mToRAx1xFYFStKVlkn5RWyp7djdI6nD9MRJRk8ufVQFvXhjvzcdy3teA72pJ2hhp1M66L7LlRFHGRZDfzoZnRmrmJGtC0ZMXcII5Crx01eDlWCbLzIY4wg5rlTRvARJ1IkS8TQK6FhcJ2iOu994g8AZGiJanCELWZ6txEUqJqnU4u02GwM7fhI5BoMvFCuRiJqblofZFBm8aRHlE3MktMSqok1pM4eFI9DxYOSTbT2d3doIanqK7raFdT5mws1CEDPUODfvzEzYQszEEXIyOxOs1O49vKPJNwXXd30EXfzt66PIZwhqvnfiDcuXgeyaz99vbYV9vLgw1Vp1IQJaJz9PjG5C56db6btFB59TV9rUVsgTokZenOqX8qRYILrB91ZESpzK1xG", 'utf-8')
def encrypt(ba):
    j = 0
    lenCipherKey = len(cipherKey)
    for i in range(len(ba)):
        ba[i] ^= cipherKey[j]
        j += 1
        if j == lenCipherKey:
            j = 0
    return ba

def encrypt_file(src, dest):
    with open(src, 'rb') as f:
        ba = bytearray(f.read())
    with open(dest, 'wb') as f:
        f.write(encrypt(ba))

# 加密配置由游戏解密
def save_dict_to_bin_file(dic, filePath):
    assert isinstance(dic, dict)
    with open(filePath, 'wb') as f:
        f.write(encrypt(bytearray(json.dumps(dic, indent = 4, sort_keys = True).encode('utf-8'))))
    assert os.path.isfile(filePath)

def get_json_obj_from_file(filePath):
    try:
        return json.loads(read_utf8_file_content(filePath))
    except Exception as e:
        return None

# 对相同结构的 dict 进行 merge 操作
def merge_dict(dSrc, dDest, bOverride):
    def _doMerge(pDest, key, value):
        if key in pDest:
            srcValue = pDest[key]
            if isinstance(srcValue, dict) and isinstance(value, dict):
                for k, v in value.items():
                    _doMerge(srcValue, k, v)
            elif isinstance(srcValue, list) and isinstance(value, list):
                for v in value:
                    srcValue.append(v)
            elif bOverride:
                # assert type(srcValue) is type(value), 'type not equal can not merge'
                pDest[key] = value
        else:
            pDest[key] = value

    for k, v in dSrc.items():
        _doMerge(dDest, k, v)

from qiniu import Auth
from qiniu import BucketManager
from qiniu import put_file, etag, urlsafe_base64_encode, CdnManager
import qiniu.config

qiniu_access_key = ''
qiniu_secret_key = ''

def qiniu_set_key(access_key, secret_key):
    global qiniu_access_key
    global qiniu_secret_key
    assert isinstance(access_key, str) and access_key, access_key
    assert isinstance(secret_key, str) and secret_key, secret_key

    qiniu_access_key = access_key
    qiniu_secret_key = secret_key

def qiniu_upload_file(bucket_name, key, filePath, downloadUrl=None, md5=None, size=None):
    assert qiniu_access_key and qiniu_secret_key
    assert os.path.isfile(filePath)

    if md5:
        fmd5 = get_file_md5(filePath)
        fsize = os.path.getsize(filePath)
        assert md5 == fmd5 and size == fsize, 'error: %s %s_%d != %s_%d' % (filePath, fmd5, fsize, md5, size)

    q = Auth(qiniu_access_key, qiniu_secret_key)
    bucket = BucketManager(q)
    ret, info = bucket.stat(bucket_name, key)
    if ret is None:
        token = q.upload_token(bucket_name, key, 300)
        ret, info = put_file(token, key, filePath)

        if ret is None:
            return qiniu_upload_file(bucket_name, key, filePath, downloadUrl, md5, size)

        assert ret['key'] == key
        assert ret['hash'] == etag(filePath)
        print('qiniu_upload_file succeed [%s] [%s] [%s]' % (bucket_name, key, filePath))
    else:
        print('qiniu_upload_file [%s] [%s] already exists do not upload' % (bucket_name, key))

    if downloadUrl and md5 and size:
        tempFile = get_temp_file_name()
        url_download_file(downloadUrl + key, tempFile, md5, size)
        os.remove(tempFile)

def qiniu_is_file_exists(bucket_name, key):
    q = Auth(qiniu_access_key, qiniu_secret_key)
    bucket = BucketManager(q)
    ret, info = bucket.stat(bucket_name, key)
    return ret != None

# def qiniu_rm_file(bucket_name, key):
#     q = Auth(qiniu_access_key, qiniu_secret_key)
#     bucket = BucketManager(q)
#     ret, info = bucket.stat(bucket_name, key)
#     print('qiniu_check_file [%s] [%s]' % (bucket_name, key), ret != None)
#     if ret:
#         print('qiniu_remove_file [%s] [%s]' % (bucket_name, key))
#         ret, info = bucket.delete(bucket_name, key)
#     else:
#         print('qiniu_no_file [%s] [%s]' % (bucket_name, key))

def qiniu_replace_file(bucket_name, key, filePath, downloadUrl=None, md5=None, size=None):
    assert qiniu_access_key and qiniu_secret_key
    assert os.path.isfile(filePath)
    q = Auth(qiniu_access_key, qiniu_secret_key)
    bucket = BucketManager(q)
    ret, info = bucket.stat(bucket_name, key)
    print('qiniu_replace_file start [%s] [%s]' % (bucket_name, key), ret != None)
    # 
    token = q.upload_token(bucket_name, key, 300)
    ret, info = put_file(token, key, filePath)
    if ret is None:
        return qiniu_replace_file(bucket_name, key, filePath, downloadUrl, md5, size)
    assert ret['key'] == key
    assert ret['hash'] == etag(filePath)
    print('qiniu_replace_file end [%s] [%s]' % (bucket_name, key))
    # 
    if downloadUrl and md5 and size:
        tempFile = get_temp_file_name()
        url_download_file(downloadUrl + key, tempFile, md5, size)
        os.remove(tempFile)

def qiniu_refresh_urls(urls):
    assert qiniu_access_key and qiniu_secret_key
    q = Auth(qiniu_access_key, qiniu_secret_key)
    cdn_manager = CdnManager(q)
    print('qiniu_refresh_urls', urls)
    result = cdn_manager.refresh_urls(urls)
    return result


def move_file_to_relative_path(filePath, relativePath, curDir=None):
    assert os.path.isfile(filePath)

    if curDir is None:
        curDir = os.getcwd()
    assert os.path.isdir()

    listDirName = relativePath.split('/')

    for i, dirName in enumerate(listDirName):
        curDir = os.path.join(curDir, dirName)
        if i == len(listDirName) - 1:
            shutil.copyfile(filePath, curDir)
        else:
            create_dir_if_not_exists(curDir)

    assert os.path.isfile(curDir)

def convert_python_2_lua_string(data, indent=1):
    if isinstance(data, str):
        data = data.replace('\r', '\\r')
        data = data.replace('\t', '\\t')
        data = data.replace('\n', '\\n')
        data = data.replace('"', '\\"')
        return '"' + data + '"'
    elif isinstance(data, bool):
        return data and 'true' or 'false'
    elif isinstance(data, (int, float)):
        return str(data)
    elif isinstance(data, list):
        ret = ['{\n']
        for d in data:
            luadata = convert_python_2_lua_string(d, indent + 1)
            if luadata:
                for i in range(indent):
                    ret.append('    ')
                ret.append(luadata)
                ret.append(',\n')
        for i in range(indent - 1):
            ret.append('    ')
        ret.append('}')

        return ''.join(ret)
    elif isinstance(data, dict):
        ret = ['{\n']
        for k, v in data.items():
            # 导到 lua 的 dict key 必须为字符串
            assert isinstance(k, str)
            luadata = convert_python_2_lua_string(v, indent + 1)
            if luadata:
                for i in range(indent):
                    ret.append('    ')
                ret.append('[%s] = %s,\n' % (convert_python_2_lua_string(k), luadata))
        for i in range(indent - 1):
            ret.append('    ')
        ret.append('}')

        print(ret)
        return ''.join(ret)
    else:
        raise Exception('convert_python_2_lua_string type [%s] not valid' % str(type(data)))

import paramiko

def _create_ssh_client(host, port, user, password = None, remote_ssh=None):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port, username=user, password=password, sock=remote_ssh)
    return client

class FabricConsole(object):
    index = 1

    def __init__(self, hosts_name, user_name, password, remoteCurDir, gateWay=""):
        print('FabricConsole', hosts_name, user_name, gateWay)
        self._gateWay = gateWay
        self._hostsName = hosts_name
        self._userName = user_name
        self._password = password
        self._remoteCurDir = remoteCurDir

        self._ssh = None
        self._hopSSh = None
        self._sftp = None

        self._doConnect()

    def _doConnect(self):
        self.closeConsole()

        if self._gateWay:
            uname, host = self._gateWay.split('@')
            self._hopSSh = _create_ssh_client(host, 22, uname)
            remote_ssh = self._hopSSh.get_transport().open_channel("direct-tcpip", 
                                                              src_addr=(host, 22), 
                                                              dest_addr=(self._hostsName, 22))
        else:
            remote_ssh = None
        
        self._ssh = _create_ssh_client(self._hostsName, 22, self._userName, self._password, remote_ssh)
        self._sftp = self._ssh.open_sftp()

    @property
    def isConnected(self):
        return self._ssh != None and self._ssh.get_transport().is_active()

    def _executeIfNotConnectedRetry(self, func):
        while True:
            while not self.isConnected:
                self._doConnect()
            func()
            if self.isConnected:
                return

    def closeConsole(self):
        if self._sftp:
            self._sftp.close()
            self._sftp = None

        if self._ssh:
            self._ssh.close()
            self._ssh = None

        if self._hopSSh:
            self._hopSSh.close()
            self._hopSSh = None

    def http_upload_file(self, nativePath, remoteFilePath, md5=None, size=None):
        assert os.path.isfile(nativePath)
        remoteFilePath = self._remoteCurDir + remoteFilePath
        print('http_upload_file [%s]--->[%s]' % (nativePath, remoteFilePath))

        self._executeIfNotConnectedRetry(lambda:self._sftp.put(nativePath, remoteFilePath))

        # validate
        if md5 and size:
            tmpF = get_temp_file_name()
            self.http_download_file(remoteFilePath, tmpF, md5, size)
            remove_file_if_exists(tmpF)

    def send_content_to_http_file(self, content, remoteFilePath):
        tempFilePath = get_temp_file_name()
        write_utf8_file_content(tempFilePath, content)
        self.http_upload_file(tempFilePath, remoteFilePath)
        remove_file_if_exists(tempFilePath)

    def send_dic_to_http_file(self, dic, remoteFilePath):
        assert isinstance(dic, dict)
        sendContent = json.dumps(dic, indent = 4, sort_keys = True)
        self.send_content_to_http_file(sendContent, remoteFilePath)
        return sendContent

    def http_download_file(self, remoteFilePath, nativePath, md5=None, size=None, bForce=True):
        remove_file_if_exists(nativePath)

        remoteFilePath = self._remoteCurDir + remoteFilePath
        print('http_download_file [%s]--->[%s]' % (remoteFilePath, nativePath))

        self._executeIfNotConnectedRetry(lambda: self._sftp.get(remoteFilePath, nativePath))

        # validate
        assert os.path.isfile(nativePath), 'http_download_file[%s] failed' % remoteFilePath
        if md5 and size:
            assert get_file_md5(nativePath) == md5
            assert os.path.getsize(nativePath) == size

    def get_content_from_http_file(self, remoteFilePath, bForce=True):
        try:
            temFilePath = get_temp_file_name()
            self.http_download_file(remoteFilePath, temFilePath, None, None, bForce)
            ret = read_utf8_file_content(temFilePath)
            os.remove(temFilePath)
        except Exception as e:
            ret = None

        return ret

    def get_dic_from_http_file(self, remoteFilePath, bForce=True):
        try:
            return json.loads(self.get_content_from_http_file(remoteFilePath, bForce))
        except Exception as e:
            return None

    @staticmethod
    def _isOutPutAborted(output):
        return len(output) > 9 and output[-9:] == 'Aborting.'

    def runCommand(self, cmd):
        print('runCommand', cmd)
        ret = [None]
        def _run():
            stdin, stdout, stderr = self._ssh.exec_command(cmd)
            output = stdout.read().decode().strip()
            print('output', output)
            ret[0] = output
            error = stderr.read().decode().strip()
            if error or self._isOutPutAborted(output):
                print('error', error)
                self.closeConsole()

        self._executeIfNotConnectedRetry(_run)
        return ret[0]

    # run op
    def http_create_dir(self, remoteDirPath):
        print('fab create dir:[%s]' % remoteDirPath)
        return self.runCommand(f'mkdir -p {self._remoteCurDir + remoteDirPath}')

    def http_rm_dir(self, remoteDirPath):
        print('fab rm dir:[%s]' % remoteDirPath)
        return self.runCommand(f'rm -rf {self._remoteCurDir + remoteDirPath}')

    def http_rm_file(self, remoteFilePath):
        print('fab rm file:[%s]' % remoteFilePath)
        return self.runCommand(f'rm -rm {self._remoteCurDir + remoteFilePath}')

class Log(object):
    def __init__(self, logPath, mode='w'):
        f = open(logPath, mode, encoding='utf-8', newline='\n')
        if f:
            self._path = logPath
            self._file = f
        else:
            raise Exception('can not open log file [%s]', logPath)

    def print_msg(self, msg):
        self._file.write(msg)
        self._file.write('\n')

    def flush(self):
        self._file.flush()

def genSheet(data, tablefmt='pipe'):
    import tabulate
    return tabulate.tabulate(data, tablefmt=tablefmt)

def format_2_lua(data, indent = 0):
    ret = []
    def write(s):
        ret.append(s)

    def writeIndent(addIndent):
        for i in range(0, indent + addIndent):
            write('\t')

    if isinstance(data, str):
        data = data.replace('\\', '\\\\')
        data = data.replace('\n', '\\n')
        data = data.replace('\t', '\\t')
        data = data.replace('"', '\\"')
        data = data.replace('\r', '')
        write('"'+data+'"')
    elif isinstance(data, (int, float)):
        write(repr(data))
    elif isinstance(data, dict):
        write('{\n')
        for k in sorted(data.keys()):
            v = data[k]
            if v is not None:
                writeIndent(indent + 1)
                write('[')
                write(format_2_lua(k, indent + 1))
                write('] = ')
                write(format_2_lua(v, indent + 1))
                write(',\n')
        writeIndent(indent)
        write('}')
    elif isinstance(data, list) or isinstance(data, tuple):
        write('{')
        isContainer = False
        for v in data:
            if isContainer or isinstance(v, list) or isinstance(v, tuple) or isinstance(v, dict):
                isContainer = True
                write('\n')
                writeIndent(indent)
            write(format_2_lua(v,indent))
            write(',')
        if isContainer:
            writeIndent(indent - 1)
        write('}')
    elif data is None:
        write('nil')
    else:
        print('serialize type [%s] not supported' % str(type(data)))

    return ''.join(ret)

__auth = ''
def _tryGetAuth():
    global __auth
    if not __auth:
        loginUrl = 'https://ght-hall.badambiz.com:47267/api/login'
        __auth = requests.post(loginUrl, json = {
                'username': 'badam-log-api',
                'password': 'r8yVIhxF4aTbRQ16',
                'recaptcha': '',
            }).text

    return __auth

def download_badam_log(url, path):
    url = url.replace('/files/', '/api/raw/')

    data = requests.get(url, headers = {
            'X-Auth': _tryGetAuth(),
        }).text

    with open(path, 'wb') as f:
        f.write(data.encode('utf-8'))

def list_badam_log_dir(url):
    url = url.replace('/files/', '/api/resources/')

    data = requests.get(url, headers = {
            'X-Auth': _tryGetAuth(),
        }).text

    # {u'isDir': False, u'name': u'res_usage20220609082619.txt', u'extension': u'.txt', u'isSymlink': False, u'modified': u'2022-06-09T19:16:07.280984124+08:00', u'mode': 420, u'path': u'/xinjiang_master/upload_content/20220609/48339964/res_usage20220609082619.txt', u'type': u'text', u'size': 13020}
    return json.loads(data)['items']

def get_lua_code(fp):
    content = []

    if os.path.isfile(fp):
        for line in read_utf8_file_lines(fp):
            line = line.strip()
            if line and not line.startswith('--'):
                content.append(line)

    return '\n'.join(content)

def get_dir_files(fp):
    assert(os.path.isdir(fp))

    dirs  = []
    files = []
    for fName in os.listdir(fp):
        path = os.path.join(fp, fName)
        if os.path.isfile(path):
            files.append(fName)
        elif os.path.isdir(path):
            dirs.append(fName)

    return dirs, files

def is_dir_empty(fp):
    for fName in os.listdir(fp):
        return False

    return True

def remove_dir_if_empty(fp):
    if is_dir_empty(fp):
        os.removedirs(fp)

def str_replace_ext(s, replaceInfo):
    ret = s
    for k, v in replaceInfo.items():
        ret = ret.replace(k, v)

    return ret

def read_utf8_file_content(path):
    assert os.path.isfile(path), path
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_utf8_file_content(path, content):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    assert os.path.isfile(path)

def read_utf8_file_lines(path):
    assert os.path.isfile(path), path
    ret = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            ret.append(line.replace('\r', ''))
    return ret

def write_utf8_file_lines(path, lines):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(lines)
    assert os.path.isfile(path)
