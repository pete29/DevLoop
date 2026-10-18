"""Which DevLoop this is.

Semantic versioning: MAJOR.MINOR.PATCH. Before 1.0 the minor
number moves with every release that adds something, the
patch number with fixes. Bump it here and add the release
to CHANGELOG.md in the same commit.
"""

VERSION = "0.13.0"

# alpha: works end to end, still changing shape; beta: proven
# on real projects, interfaces settled; "" once released.
STAGE = "alpha"
