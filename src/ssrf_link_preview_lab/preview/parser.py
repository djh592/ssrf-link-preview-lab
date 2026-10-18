import codecs
from email.message import Message
from html.parser import HTMLParser

from ssrf_link_preview_lab.preview.models import PageMetadata


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._title_depth = 0
        self._title_parts: list[str] = []
        self._open_graph_title: str | None = None
        self._twitter_title: str | None = None
        self._description: str | None = None
        self._open_graph_description: str | None = None
        self._twitter_description: str | None = None
        self._site_name: str | None = None
        self._open_graph_image: str | None = None
        self._twitter_image: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized_tag = tag.casefold()
        if normalized_tag == "title":
            self._title_depth += 1
            return
        if normalized_tag != "meta":
            return

        attributes = {name.casefold(): value for name, value in attrs}
        key = (attributes.get("property") or attributes.get("name") or "").casefold()
        content = _clean_text(attributes.get("content"))
        if content is None:
            return

        if key == "og:title" and self._open_graph_title is None:
            self._open_graph_title = content
        elif key == "twitter:title" and self._twitter_title is None:
            self._twitter_title = content
        elif key == "description" and self._description is None:
            self._description = content
        elif key == "og:description" and self._open_graph_description is None:
            self._open_graph_description = content
        elif key == "twitter:description" and self._twitter_description is None:
            self._twitter_description = content
        elif key == "og:site_name" and self._site_name is None:
            self._site_name = content
        elif key == "og:image" and self._open_graph_image is None:
            self._open_graph_image = content
        elif key == "twitter:image" and self._twitter_image is None:
            self._twitter_image = content

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title" and self._title_depth > 0:
            self._title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._title_depth > 0:
            self._title_parts.append(data)

    def metadata(self) -> PageMetadata:
        document_title = _clean_text("".join(self._title_parts))
        return PageMetadata(
            title=self._open_graph_title or self._twitter_title or document_title,
            description=(
                self._open_graph_description
                or self._twitter_description
                or self._description
            ),
            site_name=self._site_name,
            image_url=self._open_graph_image or self._twitter_image,
        )


def parse_html_metadata(body: bytes, content_type: str) -> PageMetadata:
    parser = _MetadataParser()
    parser.feed(body.decode(_extract_charset(content_type), errors="replace"))
    parser.close()
    return parser.metadata()


def _extract_charset(content_type: str) -> str:
    headers = Message()
    headers["content-type"] = content_type
    charset = headers.get_content_charset() or "utf-8"

    try:
        codecs.lookup(charset)
    except LookupError:
        return "utf-8"
    return charset


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None
