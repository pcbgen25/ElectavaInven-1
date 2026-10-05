from rest_framework.routers import SimpleRouter


class OptionalSlashRouter(SimpleRouter):
    """Accept both ``/api/components`` and ``/api/components/``.

    The Next.js proxy strips trailing slashes, so routes must not require them.
    """

    def __init__(self) -> None:
        super().__init__()
        self.trailing_slash = "/?"
