from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import traceback

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        print(f"\u27a1\ufe0f Incoming request: {request.method} {request.url}")
        try:
            response = await call_next(request)
            print(f"\u2b05\ufe0f Response: {response.status_code}")
            return response
        except Exception as e:
            print(f"\u274c Exception during request: {str(e)}")
            traceback.print_exc()
            raise e