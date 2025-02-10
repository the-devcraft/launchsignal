"""A bounded single-page audit with explicit, explainable rules."""

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from django.conf import settings


class FetchPolicyError(Exception):
    pass


def normalized_url(value):
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower()
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            raise ValueError
        if parsed.port not in (None, 443) or parsed.fragment:
            raise ValueError
        return f"https://{host}{parsed.path or '/'}" + (f"?{parsed.query}" if parsed.query else "")
    except (ValueError, UnicodeError) as exc:
        raise FetchPolicyError("https_url_required") from exc


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, timeout=8, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Connect to the address we validated, but verify TLS against the original hostname.
        raw = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def fetch_html(value):
    parsed = urlsplit(normalized_url(value))
    host = parsed.hostname
    if host not in settings.AUDIT_ALLOWED_HOSTS:
        raise FetchPolicyError("host_not_allowlisted")
    addresses = sorted(
        {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    )
    if not addresses or any(not ipaddress.ip_address(x).is_global for x in addresses):
        raise FetchPolicyError("non_public_address")
    conn = PinnedHTTPSConnection(host, addresses[0])
    try:
        target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        conn.request(
            "GET",
            target,
            headers={
                "User-Agent": "LaunchSignalAudit/0.1 (single-page audit)",
                "Accept-Encoding": "identity",
            },
        )
        response = conn.getresponse()
        if 300 <= response.status < 400:
            raise FetchPolicyError("redirect_not_allowed")
        if response.status >= 500:
            raise OSError("upstream_unavailable")
        if response.status != 200:
            raise FetchPolicyError("upstream_rejected")
        if response.getheader("Content-Type", "").split(";")[0] not in (
            "text/html",
            "application/xhtml+xml",
        ):
            raise FetchPolicyError("html_required")
        if response.getheader("Content-Encoding", "identity") != "identity":
            raise FetchPolicyError("encoded_body_rejected")
        content = response.read(524_289)
        if len(content) > 524_288:
            raise FetchPolicyError("page_too_large")
        return content.decode("utf-8", errors="replace")
    finally:
        conn.close()


def analyze(html):
    if len(html.encode()) > 524_288:
        raise FetchPolicyError("page_too_large")
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    description = soup.find("meta", attrs={"name": "description"})
    canonical = soup.find("link", rel="canonical")
    rules = [
        (
            "title",
            20,
            bool(title) and len(title) <= 70,
            "high",
            "Improve the page title",
            "A clear page title is missing or exceeds 70 characters.",
            "Write a descriptive title aligned with the page's search intent.",
        ),
        (
            "description",
            20,
            bool(description and description.get("content", "").strip()),
            "medium",
            "Add a meta description",
            "The page does not provide a usable meta description.",
            "Summarize the page and its value in a concise meta description.",
        ),
        (
            "heading",
            20,
            len(soup.find_all("h1")) == 1,
            "medium",
            "Clarify the primary heading",
            "The page should have one clear primary H1 heading.",
            "Choose one descriptive H1.",
        ),
        (
            "canonical",
            15,
            bool(canonical and canonical.get("href")),
            "medium",
            "Declare the canonical URL",
            "A canonical link is not declared.",
            "Add an absolute canonical URL for the preferred version of this page.",
        ),
        (
            "image_alt",
            25,
            all(img.has_attr("alt") for img in soup.find_all("img")),
            "high",
            "Describe meaningful images",
            "One or more images lack an alt attribute.",
            "Add descriptive alt text, or an empty alt attribute for decorative images.",
        ),
    ]
    findings = [
        {
            "code": code,
            "severity": severity,
            "title": heading,
            "explanation": explanation,
            "recommendation": recommendation,
        }
        for code, _, passed, severity, heading, explanation, recommendation in rules
        if not passed
    ]
    return sum(weight for _, weight, passed, *_ in rules if passed), findings
