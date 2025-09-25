from aiohttp import web

class KeepAliveHandler:
    def __init__(self):
        self.last_ping = None
        
    async def handle_ping(self, request):
        """Handle incoming ping requests"""
        return web.Response(text="Bot is alive and running!", status=200)

    def setup_routes(self, app):
        """Setup routes for the keep alive handler"""
        app.router.add_get("/keep-alive", self.handle_ping)
        app.router.add_get("/", self.handle_ping)  # Root path for basic health check