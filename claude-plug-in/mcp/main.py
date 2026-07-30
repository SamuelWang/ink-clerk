from shared.mcp_instance import mcp

import tools.projects  # noqa: F401
import tools.documents  # noqa: F401
import tools.drafts  # noqa: F401
import tools.import_google_doc  # noqa: F401
import resources.resources  # noqa: F401
import prompts.prompts  # noqa: F401

if __name__ == "__main__":
    mcp.run()
