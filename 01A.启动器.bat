@echo on
cd /D "%~dp0"

SET PATH=%~dp0envs\TensorRT-RTX\bin;%~dp0envs\python_embedded;%~dp0envs\python_embedded\Scripts;%~dp0envs\python_embedded\Library\bin;%PATH%

start "" pythonw launcher2.py
exit