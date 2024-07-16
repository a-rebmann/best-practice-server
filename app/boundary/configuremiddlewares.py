"""
Configures all required middlewares

This module is the entrypoint for API's middleware configuration. The middlewares themselves might
live as separate submodules under /middlewares, but they should be configured (added to app) here
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def configure_middlewares(app: FastAPI, settings) -> None:
    """Configures and adds all required middlwares to the app"""
    _configure_cors_middleware(app, settings)


def _configure_cors_middleware(app: FastAPI, settings) -> None:
    if (origins := settings.cors_origins) is not None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins.split(','),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
