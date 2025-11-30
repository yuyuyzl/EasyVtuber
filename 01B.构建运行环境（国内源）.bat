@echo on
cd /D "%~dp0"

WHERE conda
IF %ERRORLEVEL% NEQ 0 (
    if not exist "envs" mkdir envs
    if not exist "envs\miniconda3" mkdir envs\miniconda3

    IF not EXIST %~dp0envs\miniconda3\Scripts (
        @RD /S /Q %~dp0envs\miniconda3
        mkdir %~dp0envs\miniconda3
        echo "Downloading miniconda..."
        
        powershell -Command "iwr -uri 'https://repo.anaconda.com/miniconda/Miniconda3-py310_24.9.2-0-Windows-x86_64.exe' -OutFile '.\envs\miniconda3.exe'"
        if not exist %~dp0envs\miniconda3.exe (
            echo "Failed to download Miniconda installer."
            pause
            exit /b 1
        )

        echo "Installling minconda..."
        start /wait "" %~dp0envs\miniconda3.exe /S /AddToPath=0 /RegisterPython=0 /InstallationType=JustMe /D=%~dp0envs\miniconda3
        echo "Successfully install minconda"
        del envs\miniconda3.exe
    )
)

IF EXIST %~dp0envs\miniconda3\Scripts SET PATH=%~dp0envs\miniconda3\Scripts;%PATH%

call activate
call conda env list
call conda update -y --all
call conda create -y -n ezvtb_rt_venv python=3.10
call conda activate ezvtb_rt_venv
call conda env list

call conda install -y nvidia/label/cuda-12.9.0::cuda-nvcc-dev_win-64
call conda install -y pycuda -c https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/ 

call python -m pip install --upgrade pip wheel -i https://mirrors.aliyun.com/pypi/simple/
echo yes|python -m pip install nvidia-cudnn-cu12 -i https://mirrors.aliyun.com/pypi/simple/

echo yes|pip install tensorrt_cu12_libs==10.11.0.33 tensorrt_cu12_bindings==10.11.0.33 tensorrt==10.11.0.33 --extra-index-url https://pypi.nvidia.com

call python -m pip install -r requirements.txt --no-warn-script-location -i https://mirrors.aliyun.com/pypi/simple/

pause