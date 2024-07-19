import uvicorn
from app.app import SETTINGS
import ssl


if __name__ == "__main__":
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain('cert.pem', keyfile='key.pem')
    uvicorn.run(
        "app.app:APP",
        host=SETTINGS.host,
        port=SETTINGS.port,
        root_path=SETTINGS.root_path,
        log_level=SETTINGS.log_level,
        app_dir="",
        reload=SETTINGS.develop,
        workers=SETTINGS.n_workers,
        ssl_keyfile=SETTINGS.ssl_keyfile,
        ssl_certfile=SETTINGS.ssl_certfile,
    )