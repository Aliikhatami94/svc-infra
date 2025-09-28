from typing import Optional


class FastApiException(Exception):
    """
    Application error that should be rendered as Problem Details.
    """

    def __init__(
        self,
        title: str,
        detail: Optional[str] = None,
        status_code: int = 400,
        *,
        code: str | None = None
    ):
        self.title = title
        self.detail = detail
        self.status_code = status_code
        self.code = code or title.replace(" ", "_").upper()
