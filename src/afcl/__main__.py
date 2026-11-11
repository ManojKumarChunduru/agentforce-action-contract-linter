"""Allow `python -m afcl`, which is how a CI step with no console script entry calls it."""

import sys

from afcl.cli import main

sys.exit(main())
