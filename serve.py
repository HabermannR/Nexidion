"""Cross-platform production launcher.

Linux containers normally use Gunicorn. Windows and bare-metal installations can
run this module, which uses Waitress and the exact same Flask application.
"""
import os

from waitress import serve
from wsgi import app


if __name__ == "__main__":
    serve(app, host=os.getenv("NEXIDION_HOST", "0.0.0.0"),
          port=int(os.getenv("NEXIDION_PORT", "5001")))
