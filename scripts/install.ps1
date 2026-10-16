# Instalador de ComfyUI + Chroma1-HD para Windows + NVIDIA (pensado para RTX 3060 12GB)
# Uso normal: doble clic en INSTALAR.bat
# Uso avanzado:
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -InstallDir "D:\IA" -SinSage -SinModelos
# Se puede volver a ejecutar: salta lo que ya esta hecho y reanuda descargas cortadas.

param(
    [string]$InstallDir = "C:\IA",
    [switch]$SinSage,      # no instalar SageAttention / Triton
    [switch]$SinModelos    # no descargar los modelos (si ya los tienes)
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest es 10x mas lento con la barra de progreso

# ------------------------------------------------------------------ versiones fijadas
$ComfyVersion   = "v0.41.0"   # v0.41.1 no publico paquete portable; 0.41.0 es la ultima que lo tiene
$ComfyUrl       = "https://github.com/comfyanonymous/ComfyUI/releases/download/$ComfyVersion/ComfyUI_windows_portable_nvidia.7z"
$SevenZipUrl    = "https://www.7-zip.org/a/7zr.exe"
$VcRedistUrl    = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
$PyIncludeLibs  = "https://github.com/woct0rdho/triton-windows/releases/download/v3.0.0-windows.post1/python_3.13.2_include_libs.zip"
$SageVersion    = "1.0.6"
$MinDriver      = 580   # el portable usa PyTorch cu130 -> driver NVIDIA 580 o superior

$Models = @(
    @{ Name = "Chroma1-HD-fp8mixed.safetensors"; Dir = "diffusion_models"; MinGB = 8.0
       Url  = "https://huggingface.co/Comfy-Org/Chroma1-HD_repackaged/resolve/main/split_files/diffusion_models/Chroma1-HD-fp8mixed.safetensors" },
    @{ Name = "t5xxl_fp8_e4m3fn_scaled.safetensors"; Dir = "text_encoders"; MinGB = 4.5
       Url  = "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn_scaled.safetensors" },
    @{ Name = "ae.safetensors"; Dir = "vae"; MinGB = 0.3
       Url  = "https://huggingface.co/Comfy-Org/Lumina_Image_2.0_Repackaged/resolve/main/split_files/vae/ae.safetensors" },
    @{ Name = "4x_foolhardy_Remacri.safetensors"; Dir = "upscale_models"; MinGB = 0.05
       Url  = "https://huggingface.co/martin-rizzo/ESRGAN-4x/resolve/main/4x_foolhardy_Remacri.safetensors" }
)

# ------------------------------------------------------------------ utilidades
$RepoDir   = Split-Path -Parent $PSScriptRoot
$Downloads = Join-Path $InstallDir "_descargas"
$Portable  = Join-Path $InstallDir "ComfyUI_windows_portable"
$Python    = Join-Path $Portable "python_embeded\python.exe"
$Comfy     = Join-Path $Portable "ComfyUI"

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    OK  $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    !!  $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host ""; Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

# Descarga con curl.exe (incluido en Windows 10/11): reanuda, reintenta y sigue redirecciones.
function Get-File($url, $dest, [double]$minGB = 0) {
    if (Test-Path "$dest.ok") { Ok "ya descargado: $(Split-Path -Leaf $dest)"; return }
    $part = "$dest.part"
    Write-Host "    descargando $(Split-Path -Leaf $dest) ..."
    & curl.exe -L --fail --retry 10 --retry-delay 5 --retry-all-errors -C - -o $part $url
    if ($LASTEXITCODE -ne 0) { Fail "fallo la descarga de $url (codigo $LASTEXITCODE). Vuelve a ejecutar el instalador para reanudar." }
    $sizeGB = (Get-Item $part).Length / 1GB
    if ($minGB -gt 0 -and $sizeGB -lt $minGB) {
        Remove-Item $part -Force
        Fail "el archivo $(Split-Path -Leaf $dest) pesa solo $([math]::Round($sizeGB,2)) GB (esperado >= $minGB GB). Borrado; reintenta."
    }
    if (Test-Path $dest) { Remove-Item $dest -Force }
    Move-Item $part $dest
    New-Item "$dest.ok" -ItemType File -Force | Out-Null
    Ok "$(Split-Path -Leaf $dest) ($([math]::Round($sizeGB * 1024)) MB)"
}

function Pip { & $Python -s -m pip --disable-pip-version-check @args | Out-Host; return $LASTEXITCODE }

# ------------------------------------------------------------------ 1. comprobaciones
Step "Comprobando el sistema"
if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) { Fail "no se encontro curl.exe (viene con Windows 10/11)." }

$smi = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
if (-not $smi) { Fail "no se encontro nvidia-smi. Instala el driver NVIDIA mas reciente: https://www.nvidia.com/drivers" }
$gpuInfo = @(& nvidia-smi.exe --query-gpu=name,memory.total,driver_version --format=csv,noheader)[0]
Ok "GPU: $gpuInfo"
$driver = [double](($gpuInfo -split ",")[2].Trim() -split "\.")[0]
if ($driver -lt $MinDriver) {
    Fail "tu driver NVIDIA es $driver; esta version de ComfyUI necesita $MinDriver o superior. Actualizalo (GeForce Experience / nvidia.com) y vuelve a ejecutar."
}

New-Item $InstallDir -ItemType Directory -Force | Out-Null
New-Item $Downloads  -ItemType Directory -Force | Out-Null
$drive = (Get-Item $InstallDir).PSDrive
$freeGB = [math]::Round($drive.Free / 1GB, 1)
$needGB = 40
if (Test-Path $Portable) { $needGB = 20 }
if ($freeGB -lt $needGB) { Fail "solo hay $freeGB GB libres en $($drive.Name):. Se necesitan unos $needGB GB." }
Ok "espacio libre en $($drive.Name): $freeGB GB"

# ------------------------------------------------------------------ 2. Visual C++ runtime
Step "Visual C++ Redistributable (lo necesitan PyTorch y Triton)"
$vc = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" -ErrorAction SilentlyContinue
if ($vc -and $vc.Installed -eq 1 -and $vc.Minor -ge 42) {
    Ok "ya instalado ($($vc.Version))"
} else {
    $vcExe = Join-Path $Downloads "vc_redist.x64.exe"
    Get-File $VcRedistUrl $vcExe
    Write-Host "    instalando (Windows pedira permiso de administrador)..."
    $p = Start-Process $vcExe -ArgumentList "/install", "/quiet", "/norestart" -Verb RunAs -Wait -PassThru
    if ($p.ExitCode -notin 0, 1638, 3010) { Warn "vc_redist termino con codigo $($p.ExitCode); si ComfyUI falla con c10.dll instalalo a mano: $VcRedistUrl" }
    else { Ok "instalado" }
}

# ------------------------------------------------------------------ 3. ComfyUI portable
Step "ComfyUI $ComfyVersion (portable, NVIDIA)"
if (Test-Path $Python) {
    Ok "ya existe en $Portable"
} else {
    $seven = Join-Path $Downloads "7zr.exe"
    Get-File $SevenZipUrl $seven
    $archive = Join-Path $Downloads "ComfyUI_$ComfyVersion.7z"
    Get-File $ComfyUrl $archive 1.0
    Write-Host "    descomprimiendo (tarda unos minutos)..."
    & $seven x $archive "-o$InstallDir" -y | Out-Null
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Python)) { Fail "no se pudo descomprimir $archive" }
    Ok "instalado en $Portable"
}
$torchVer = (& $Python -s -c "import torch;print(torch.__version__)").Trim()
Ok "PyTorch $torchVer"
& $Python -s -c "import torch,sys;sys.exit(0 if torch.cuda.is_available() else 1)"
if ($LASTEXITCODE -ne 0) { Fail "PyTorch no ve la GPU. Actualiza el driver NVIDIA." }
Ok "CUDA disponible"

# ------------------------------------------------------------------ 4. dependencias
Step "Dependencias de ComfyUI y ComfyUI-Manager"
if ((Pip install -r (Join-Path $Comfy "requirements.txt")) -ne 0) { Fail "pip no pudo instalar requirements.txt" }
if ((Pip install -r (Join-Path $Comfy "manager_requirements.txt")) -ne 0) { Fail "pip no pudo instalar ComfyUI-Manager" }
Ok "dependencias al dia"

# ------------------------------------------------------------------ 5. SageAttention (opcional)
$useSage = $false
if ($SinSage) {
    Step "SageAttention: omitido (-SinSage)"
} else {
    Step "Optimizador: Triton + SageAttention"
    $pyDir = Split-Path -Parent $Python
    if (-not (Test-Path (Join-Path $pyDir "include\Python.h"))) {
        $zip = Join-Path $Downloads "python_3.13.2_include_libs.zip"
        Get-File $PyIncludeLibs $zip
        Expand-Archive $zip -DestinationPath $pyDir -Force
        Ok "cabeceras de Python copiadas (include/libs)"
    }
    # triton-windows 3.X va con PyTorch 2.(X+4): 2.9->3.5, 2.10->3.6, 2.11->3.7 ...
    $torchMinor = [int](($torchVer -split "\.")[1])
    $tMinor = $torchMinor - 4
    $tritonSpec = "triton-windows>=3.$tMinor,<3.$($tMinor + 1)"
    $r1 = Pip install $tritonSpec
    $r2 = Pip install "sageattention==$SageVersion"
    if ($r1 -ne 0 -or $r2 -ne 0) {
        Warn "no se pudo instalar Triton/SageAttention; ComfyUI funcionara igual sin el (un poco mas lento)."
    } else {
        Write-Host "    probando SageAttention en la GPU (la primera vez compila, ~1 min)..."
        & $Python -s (Join-Path $PSScriptRoot "test_sage.py")
        if ($LASTEXITCODE -eq 0) { $useSage = $true; Ok "SageAttention funciona: activado" }
        else { Warn "SageAttention no paso la prueba; se arrancara sin el." }
    }
}

# ------------------------------------------------------------------ 6. modelos
if ($SinModelos) {
    Step "Modelos: omitidos (-SinModelos)"
} else {
    Step "Modelos de Chroma1-HD + upscaler (~14 GB en total)"
    foreach ($m in $Models) {
        $dir = Join-Path $Comfy "models\$($m.Dir)"
        New-Item $dir -ItemType Directory -Force | Out-Null
        Get-File $m.Url (Join-Path $dir $m.Name) $m.MinGB
    }
}

New-Item (Join-Path $Comfy "models\loras") -ItemType Directory -Force | Out-Null

# ------------------------------------------------------------------ 7. nodos propios + workflows
Step "Nodos del Panel Chroma"
$nodeSrc = Join-Path $RepoDir "custom_nodes\ComfyUI-ChromaPanel"
$nodeDst = Join-Path $Comfy "custom_nodes\ComfyUI-ChromaPanel"
if (Test-Path $nodeDst) { Remove-Item $nodeDst -Recurse -Force }
Copy-Item $nodeSrc $nodeDst -Recurse -Force
Ok "instalados en ComfyUI\custom_nodes\ComfyUI-ChromaPanel"

Step "Workflows"
$wfDir = Join-Path $Comfy "user\default\workflows"
New-Item $wfDir -ItemType Directory -Force | Out-Null
Copy-Item (Join-Path $RepoDir "workflows\*.json") $wfDir -Force
Copy-Item (Join-Path $RepoDir "workflows\chroma_referencia_ejemplo.png") (Join-Path $Comfy "input") -Force
Ok "copiados a ComfyUI\user\default\workflows (panel 'Workflows' de ComfyUI)"

# ------------------------------------------------------------------ 8. lanzador
Step "Creando el lanzador"
$flags = "--windows-standalone-build --enable-manager --preview-method auto"
if ($useSage) { $flags += " --use-sage-attention" }
$launcher = Join-Path $InstallDir "INICIAR_ComfyUI_Chroma.bat"
@"
@echo off
title ComfyUI - Chroma
cd /d "%~dp0ComfyUI_windows_portable"
.\python_embeded\python.exe -s ComfyUI\main.py $flags
echo.
echo ComfyUI se cerro. Si fue un error, copia el texto de arriba para revisarlo.
pause
"@ | Set-Content -Path $launcher -Encoding ASCII
Ok $launcher

$lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "ComfyUI Chroma.lnk"
try {
    $sh = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
    $sh.TargetPath = $launcher
    $sh.WorkingDirectory = $InstallDir
    $sh.Save()
    Ok "acceso directo en el escritorio"
} catch { Warn "no se pudo crear el acceso directo (no es grave)" }

# ------------------------------------------------------------------ fin
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host " LISTO. Abre 'ComfyUI Chroma' en el escritorio."                       -ForegroundColor Green
Write-Host " En el navegador: panel izquierdo 'Workflows' ->"                      -ForegroundColor Green
Write-Host "   Chroma_0_Panel              (RECOMENDADO: todo en un panel + LoRAs)" -ForegroundColor Green
Write-Host "   Chroma_1_TextoAImagen       (texto a imagen)"                       -ForegroundColor Green
Write-Host "   Chroma_2_ImagenReferencia   (imagen de referencia / img2img)"      -ForegroundColor Green
Write-Host " SageAttention: $(if ($useSage) {'activado'} else {'desactivado'})"   -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green
