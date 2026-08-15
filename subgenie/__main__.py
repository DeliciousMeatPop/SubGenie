"""Allow ``python -m subgenie`` to work identically to the ``subgenie`` command."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
