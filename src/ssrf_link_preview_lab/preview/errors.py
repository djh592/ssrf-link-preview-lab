class UnsupportedContentTypeError(Exception):
    def __init__(self, content_type: str | None) -> None:
        rendered_type = content_type or "missing Content-Type"
        super().__init__(f"The upstream response is not HTML ({rendered_type}).")
