@echo on
REM ========================================================================
REM IMPORTANT: Before running this script, please make sure to:
REM 1. Checkout to the release_package branch: git checkout release_package
REM 2. Rebase with the latest changes: git rebase main
REM ========================================================================

REM ========================================================================
REM Version Configuration
REM ========================================================================
SET TENSORRT_VERSION=1.4.0.76
SET CUDA_VERSION=12.9
SET CUDA_VERSION_FULL=12.9.1
SET PYTHON_VERSION=3.10
SET MINICONDA_VERSION=Miniconda3-py310_24.9.2-0-Windows-x86_64

REM ========================================================================
REM Download URLs
REM ========================================================================
SET TENSORRT_DOWNLOAD_URL=https://developer.nvidia.com/downloads/trt/rtx_sdk/secure/1.4/TensorRT-RTX-%TENSORRT_VERSION%-Windows-amd64-cuda-%CUDA_VERSION%-Release-external.zip
SET MINICONDA_DOWNLOAD_URL=https://repo.anaconda.com/miniconda/%MINICONDA_VERSION%.exe

REM ========================================================================
REM Derived Paths (auto-generated from versions)
REM ========================================================================
SET TENSORRT_DIR_NAME=TensorRT-RTX-%TENSORRT_VERSION%_cu%CUDA_VERSION%
SET TENSORRT_WHL_NAME=tensorrt_rtx-%TENSORRT_VERSION%-cp310-none-win_amd64.whl

cd /D "%~dp0"

if not exist "envs" mkdir envs
if not exist "envs\miniconda3" mkdir envs\miniconda3

IF not EXIST %~dp0envs\%TENSORRT_DIR_NAME%\bin (
    @RD /S /Q %~dp0envs\%TENSORRT_DIR_NAME%
    cd /D "%~dp0\envs"
    curl -L -f -o trt_rtx.zip %TENSORRT_DOWNLOAD_URL%
    tar -xf trt_rtx.zip "TensorRT-RTX-%TENSORRT_VERSION%" && ren "TensorRT-RTX-%TENSORRT_VERSION%" "TensorRT-RTX" && del trt_rtx.zip
    cd /D "%~dp0"
)

IF not EXIST %~dp0envs\miniconda3\Scripts (
    @RD /S /Q %~dp0envs\miniconda3
    mkdir %~dp0envs\miniconda3
    echo "Downloading miniconda..."
    powershell -Command "Invoke-WebRequest -Uri '%MINICONDA_DOWNLOAD_URL%' -OutFile '.\envs\miniconda3.exe' -UseBasicParsing -Headers @{'User-Agent'='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}"

    echo "Installing miniconda..."
    start /wait "" %~dp0envs\miniconda3.exe /S /AddToPath=0 /RegisterPython=0 /InstallationType=JustMe /D=%~dp0envs\miniconda3
    echo "Successfully installed miniconda, now cleaning up the installer..."
    del envs\miniconda3.exe
)

SET PATH=%~dp0envs\%TENSORRT_DIR_NAME%\bin;%~dp0envs\miniconda3\Scripts;%PATH%

call activate
call conda env list
call conda update -y --all
call conda create -n ezvtb_rt_venv_release python=%PYTHON_VERSION% -y
call conda activate ezvtb_rt_venv_release
call conda env list

call conda install -y conda-pack
call conda install -y conda-forge::pycuda 
call conda install -y -c nvidia/label/cuda-%CUDA_VERSION_FULL% cuda-nvcc-dev_win-64 cudnn cuda-runtime

call conda-pack -n ezvtb_rt_venv_release -o %~dp0envs\python_embedded --format no-archive


SET PATH=%~dp0envs\python_embedded;%~dp0envs\python_embedded\Scripts;%~dp0envs\python_embedded\Library\bin;%PATH%
call python -m pip install %~dp0envs\TensorRT-RTX\python\%TENSORRT_WHL_NAME%
call python -m pip install -r requirements.txt --no-warn-script-location

@RD /S /Q %~dp0envs\miniconda3
pause