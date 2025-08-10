class FastApiException(Exception):
    def __init__(self, error: str, detail: str = None, status_code: int = 400):
        self.error = error
        self.detail = detail
        self.status_code = status_code