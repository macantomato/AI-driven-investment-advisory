import azure.functions as func
from azure.functions import AsgiMiddleware
from .main import app

asgi = AsgiMiddleware(app)
def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    return asgi.handle(req, context)
