from app.tools.drive_search import drive_search_tool
from app.tools.registry import get_tool_registry
from app.tools.vector_search import vector_search_tool
from app.tools.web_scrape import web_scrape_tool
from app.tools.web_search import web_search_tool


def register_default_tools() -> None:
    registry = get_tool_registry()
    registry.register(web_search_tool)
    registry.register(web_scrape_tool)
    registry.register(drive_search_tool)
    registry.register(vector_search_tool)
