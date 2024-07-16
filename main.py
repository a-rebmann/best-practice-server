import uvicorn
from app.app import SETTINGS


if __name__ == "__main__":
    uvicorn.run(
        "app.app:APP",
        host=SETTINGS.host,
        port=SETTINGS.port,
        root_path=SETTINGS.root_path,
        log_level=SETTINGS.log_level,
        app_dir="",
        reload=SETTINGS.develop,
        workers=SETTINGS.n_workers,
    )