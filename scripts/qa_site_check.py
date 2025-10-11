import re
import textwrap
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import List, Optional, Tuple
from urllib import parse, request

BASE = "https://248c2942.nlping.pages.dev"
PATHS = [
    "/",
    "/index.html",
    "/blog.html",
    "/audio.html",
    "/bright_tranings.html",
    "/free_and_only.html",
    "/creation_of_reality-webinar-reg.html",
    "/7ul_2013.html",
    "/32347D7E-F4267-B9D62464.html",
    "/training10k.html",
    "/konstantin_pukhov.html",
    "/p/indexc1c8.html",
    "/print1178.html",
    "/rss/index.html",
]

INTERNAL_LINK_SAMPLE = {
    "/32347D7E-F4267-B9D62464.html": 2,
    "/training10k.html": 2,
}

META_CHARSET_RE = re.compile(r"<meta[^>]*charset=['\"]?([\w-]+)", re.IGNORECASE)
META_HTTP_EQUIV_RE = re.compile(
    r"<meta[^>]*http-equiv=['\"]content-type['\"][^>]*content=['\"]text/html;\s*charset=([\w-]+)",
    re.IGNORECASE,
)
XML_DECL_RE = re.compile(r"<\?xml[^>]*encoding=['\"]([\w-]+)['\"]", re.IGNORECASE)
HREF_RE = re.compile(r"href=['\"]([^'\"]+)['\"]", re.IGNORECASE)
DOUBLE_DOMAIN_RE = re.compile(r"nlping\.ru/nlping\.ru", re.IGNORECASE)
NON_READABLE_RE = re.compile(r"\ufffd")


@dataclass
class PageReport:
    url: str
    status: Optional[int] = None
    final_url: Optional[str] = None
    charset: Optional[str] = None
    text_readable: bool = True
    sample_text: str = ""
    link_issues: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def status_display(self) -> str:
        if self.status is None:
            return "нет ответа"
        if self.final_url and self.final_url != self.url:
            return f"{self.status} → {self.final_url}"
        return str(self.status)

    def link_issue_display(self) -> str:
        return "; ".join(self.link_issues) if self.link_issues else "—"

    def notes_display(self) -> str:
        return "; ".join(self.notes) if self.notes else "—"


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        clean = data.strip()
        if clean:
            self.chunks.append(clean)

    def text(self) -> str:
        return " ".join(self.chunks)


def detect_charset(text: str) -> Optional[str]:
    for pattern in (META_CHARSET_RE, META_HTTP_EQUIV_RE, XML_DECL_RE):
        match = pattern.search(text)
        if match:
            return match.group(1).lower()
    return None


def collect_sample_text(html: str) -> str:
    parser = TextExtractor()
    parser.feed(html)
    combined = parser.text()
    if not combined:
        return ""
    return textwrap.shorten(combined, width=140, placeholder="…")


def find_double_domain_links(html: str) -> List[str]:
    results = []
    for href in HREF_RE.findall(html):
        if DOUBLE_DOMAIN_RE.search(href):
            results.append(href)
    return results


def fetch_url(url: str) -> Tuple[Optional[request.addinfourl], Optional[str]]:
    req = request.Request(url, headers={"User-Agent": "nlping-checker/1.0"})
    try:
        return request.urlopen(req, timeout=20), None
    except Exception as exc:  # pragma: no cover - network errors
        return None, str(exc)


def decode_body(response: request.addinfourl) -> str:
    raw = response.read()
    charset = response.headers.get_content_charset() or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def check_internal_links(path: str, html: str, max_links: int) -> List[str]:
    checked = []
    results = []
    for href in HREF_RE.findall(html):
        if href.startswith("http") and not href.startswith(BASE):
            continue
        if href.startswith("mailto:") or href.startswith("#") or href.startswith("//"):
            continue
        candidate = parse.urljoin(BASE + path, href)
        if not candidate.startswith(BASE):
            continue
        if candidate in checked:
            continue
        checked.append(candidate)
        response, error = fetch_url(candidate)
        if response is None:
            results.append(f"{href} → ошибка загрузки ({error})")
        else:
            status = response.getcode()
            final_url = response.geturl()
            results.append(f"{href} → {status} ({final_url})")
        if len(results) >= max_links:
            break
    if not results:
        results.append("внутренние ссылки не найдены")
    return results


def fetch_page(path: str) -> PageReport:
    full_url = parse.urljoin(BASE, path)
    report = PageReport(url=full_url)
    response, error = fetch_url(full_url)
    if response is None:
        report.text_readable = False
        report.notes.append(f"ошибка загрузки: {error}")
        return report

    report.status = response.getcode()
    report.final_url = response.geturl()
    text = decode_body(response)
    report.charset = detect_charset(text) or response.headers.get_content_charset()
    report.text_readable = not bool(NON_READABLE_RE.search(text))
    report.sample_text = collect_sample_text(text)
    report.link_issues = find_double_domain_links(text)

    if path in INTERNAL_LINK_SAMPLE:
        report.notes.extend(check_internal_links(path, text, INTERNAL_LINK_SAMPLE[path]))

    if path == "/rss/index.html" and report.sample_text:
        report.sample_text = report.sample_text.split(" ")[0]
    return report


def build_markdown_table(reports: List[PageReport]) -> str:
    header = "| URL | Статус / финальный URL | Charset | Текст читабелен? | Проблемы со ссылками | Заметки |"
    separator = "|---|---|---|---|---|---|"
    rows = [header, separator]
    for report in reports:
        status = report.status_display()
        charset = report.charset or "—"
        readable = "да" if report.text_readable else "нет"
        problems = report.link_issue_display()
        notes = report.notes_display()
        rows.append(
            f"| {report.url} | {status} | {charset} | {readable} | {problems} | {notes} |"
        )
    return "\n".join(rows)


def build_summary(reports: List[PageReport]) -> str:
    ok_pages = [r.url for r in reports if r.status == 200 and r.text_readable]
    charset_issues = [
        r for r in reports if r.status and r.charset and r.charset.lower() != "utf-8"
    ]
    missing_charset = [r for r in reports if r.status and not r.charset]
    link_problems = [r for r in reports if r.link_issues]
    failed = [r for r in reports if r.status is None]

    lines = ["- Страницы без нареканий: " + (", ".join(ok_pages) if ok_pages else "нет"),]
    if charset_issues:
        lines.append(
            "- Обнаружены страницы с неожиданной кодировкой: "
            + ", ".join(f"{r.url} ({r.charset})" for r in charset_issues)
        )
    if missing_charset:
        lines.append(
            "- У ряда страниц не указан charset: "
            + ", ".join(r.url for r in missing_charset)
        )
    if link_problems:
        lines.append(
            "- Найдены потенциальные SEO-проблемы (дублированные домены в ссылках): "
            + ", ".join(
                f"{r.url}: {', '.join(r.link_issues)}" for r in link_problems
            )
        )
    else:
        lines.append("- Новых SEO-проблем со ссылками не обнаружено")

    if failed:
        lines.append(
            "- Проверку не удалось выполнить для: "
            + ", ".join(f"{r.url} ({r.notes_display()})" for r in failed)
        )
    else:
        lines.append("- Все страницы успешно проверены")
    return "\n".join(lines)


def main() -> None:
    reports = [fetch_page(path) for path in PATHS]
    table = build_markdown_table(reports)
    summary = build_summary(reports)
    print(table)
    print()
    print(summary)


if __name__ == "__main__":
    main()
