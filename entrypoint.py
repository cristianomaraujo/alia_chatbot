"""Make the Railway volume writable, then drop privileges before serving."""
import os
from pathlib import Path
path=Path(os.getenv('DATA_DIR','/data'));path.mkdir(parents=True,exist_ok=True)
if os.getuid()==0:
    os.chown(path,10001,10001)
    for item in path.iterdir():
        if item.is_file() and not item.is_symlink():os.chown(item,10001,10001)
    os.setgid(10001);os.setuid(10001)
os.execvp('uvicorn',['uvicorn','app.main:app','--host','0.0.0.0','--port',os.getenv('PORT','8000'),'--workers','1'])
