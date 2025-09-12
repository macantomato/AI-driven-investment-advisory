import azure.functions as func
from azure.functions import AsgiMiddleware

# import the FastAPI app ond folder up
from ..main import app

# Entry point Azure Functions calls
def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    asgi = AsgiMiddleware(app)
    return asgi.handle(req, context)