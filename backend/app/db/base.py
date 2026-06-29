"""Import every model here so Base.metadata knows about all tables.

create_all() (and later Alembic autogenerate) only sees models that have been
imported, so this single file is the one place that pulls them all in.
"""

from app.db.session import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.camera import Camera  # noqa: F401
from app.models.event import Event  # noqa: F401
from app.models.alert import Alert  # noqa: F401
