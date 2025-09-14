# Welcome to Cloud Functions for Firebase for Python!
# To get started, simply uncomment the below code or create your own.
# Deploy with `firebase deploy`

from firebase_functions import https_fn
from firebase_admin import initialize_app
from server import app as fastapi_app
import asgiref.wsgi

# initialize_app()

@https_fn.on_request()
def api(request):
    """
    An ASGI-WSGI adapter to run FastAPI with Firebase Cloud Functions.
    This allows us to deploy the entire FastAPI app as a single function.
    """
    wsgi_app = asgiref.wsgi.WsgiToAsgi(fastapi_app)
    return wsgi_app(request)