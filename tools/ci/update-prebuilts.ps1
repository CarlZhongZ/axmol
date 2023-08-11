$VER=$args[0]
echo "VER=$VER"

$AX_ROOT=(Resolve-Path "$PSScriptRoot/../..").Path
echo "AX_ROOT=$AX_ROOT"

$pwsh_ver = $PSVersionTable.PSVersion.ToString()

function mkdirs([string]$path) {
    if (!(Test-Path $path -PathType Container)) {
        New-Item $path -ItemType Directory 1>$null
    }
}

function download_file($url, $out, $force = $false) {
    if(Test-Path $out -PathType Leaf) { 
        if (!$force) {
            return
        }
        Remove-Item $out
    }
    Write-Host "Downloading $url to $out ..."
    if ($pwsh_ver -ge '7.0') {
        curl -L $url -o $out
    }
    else {
        Invoke-WebRequest -Uri $url -OutFile $out
    }
}

function download_and_expand($url, $out, $dest) {
    download_file $url $out
    if($out.EndsWith('.zip')) {
        Expand-Archive -Path $out -DestinationPath $dest
    } elseif($out.EndsWith('.tar.gz')) {
        if (!$dest.EndsWith('/')) {
            mkdirs $dest
        }
        tar xvf "$out" -C $dest
    } elseif($out.EndsWith('.sh')) {
        chmod 'u+x' "$out"
        mkdirs $dest
    }
}

# download version manifest
cd $AX_ROOT
mkdirs ./tmp

# ensure yaml parser module
if ($null -eq (Get-Module -ListAvailable -Name powershell-yaml)) {
    Install-Module -Name powershell-yaml -Force -Repository PSGallery -Scope CurrentUser
}

# check upstream prebuilts version
download_file "https://github.com/axmolengine/buildware/releases/download/$VER/verlist.yml" "./tmp/verlist.yml" $true
$newVerList = ConvertFrom-Yaml -Yaml (Get-Content './tmp/verlist.yml' -raw)
if ($newVerList.GetType() -eq [string]) {
    throw "Download version manifest file verlist.yml fail"
}

$myVerList = ConvertFrom-Yaml -Yaml (Get-Content './thirdparty/prebuilts.yml' -raw)
$updateCount = 0

function update_lib
{
    $lib_name=$args[0]
    $lib_folder=$args[1]
    echo "lib_name=$lib_name"

    $myVer = $myVerList[$lib_name]
    if ($newVerList[$lib_name] -eq $myVer) {
        Write-Host "No update for lib: $lib_name, version: $myVer, skip it"
        return
    }

    $lib_dir="./thirdparty/$lib_folder$lib_name"
    $prebuilt_dir="$lib_dir/prebuilt"
    $inc_dir="$lib_dir/include"
    
    echo "Updating lib files for ${lib_dir} from ./tmp/package_$VER/$lib_name ..."

    download_and_expand "https://github.com/axmolengine/build1k/releases/$VER/$lib_name.zip" "./tmp/package_$VER/$lib_name.zip" "./tmp/package_$VER"

    rm -rf $prebuilt_dir
    cp -r ./tmp/package_$VER/$lib_name/prebuilt $lib_dir/
    
    if ( Test-Path "./tmp/package_$VER/$lib_name/include" -PathType Container ) {
        echo "Update inc files for ${lib_dir}"
        rm -rf $inc_dir
        cp -r ./tmp/package_$VER/$lib_name/include $lib_dir/
    }

    ++$updateCount
}

echo "Updating libs ..."

$libs_list = @('angle', 'curl', 'jpeg-turbo', 'openssl', 'zlib')

# update libs
foreach($lib_name in $libs_list) {
    update_lib $lib_name
}

update_lib luajit lua/

# update README.md
$content = $(Get-Content -Path ./thirdparty/README.md.in -raw)
foreach ($item in $newVerList.GetEnumerator() )
{
    $key = ([Regex]::Replace($item.Name, '-', '_')).ToUpper()
    $key = "${key}_VERSION"
    $content = $content -replace "\$\{$key\}",$item.Value
}
Set-Content -Path ./thirdparty/README.md -Value "$content"
Copy-Item -Path './tmp/verlist.yml' './thirdparty/prebuilts.yml' -Force

if ($updateCount -eq 0) {
    echo "No any lib need update."
    if ("$env.RUNNER_OS" -ne "") {
        echo "AX_PREBUILTS_NO_UPDATE=true" >> $GITHUB_ENV
    }
}
