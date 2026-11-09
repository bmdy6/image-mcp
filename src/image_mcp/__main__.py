"""Allow the package to run with the current Python interpreter."""
import sys

from .cli import main

sys.exit(main())
