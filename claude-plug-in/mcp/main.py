from mcp.server.fastmcp import FastMCP

mcp = FastMCP("inkclerk")

import tools.projects  # noqa: F401
import tools.documents  # noqa: F401
import tools.drafts  # noqa: F401
# import tools.import_google_doc
# import resources.resources
# import prompts.prompts

if __name__ == "__main__":
    mcp.run()
