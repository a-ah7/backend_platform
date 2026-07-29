import json
import re
import sys
from html import unescape
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, unquote, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


REQUEST_TIMEOUT = 15
MAX_EXTRA_PAGES = 8
MAX_RESULT_ITEMS = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Cache-Control": "no-cache",
}

EMAIL_REGEX = re.compile(
    r"(?<![A-Za-z0-9._%+\-])"
    r"([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,63})"
    r"(?![A-Za-z0-9._%+\-])",
    re.IGNORECASE,
)

OBFUSCATED_EMAIL_REGEX = re.compile(
    r"([A-Za-z0-9._%+\-]+)\s*"
    r"(?:\[\s*at\s*\]|\(\s*at\s*\)|\{\s*at\s*\}|\s+at\s+)\s*"
    r"([A-Za-z0-9.\-]+?)\s*"
    r"(?:\[\s*dot\s*\]|\(\s*dot\s*\)|\{\s*dot\s*\}|\s+dot\s+)\s*"
    r"([A-Za-z]{2,63})",
    re.IGNORECASE,
)

PHONE_REGEX = re.compile(
    r"(?<![\w@])"
    r"(?:\+|00)?\s*"
    r"(?:\(\s*\d{1,5}\s*\)|\d)"
    r"[\d\s().\-–—/]{4,}\d"
    r"(?:\s*(?:ext\.?|extension|x)\s*\d{1,6})?"
    r"(?![\w@])",
    re.IGNORECASE,
)

LABELED_PHONE_REGEX = re.compile(
    r"(?:phone|telephone|tel\.?|mobile|mob\.?|call|whatsapp|contact\s*(?:number|no\.?)?|"
    r"هاتف|الهاتف|تلفون|موبايل|جوال|واتساب|اتصال|اتصل)"
    r"\s*[:：\-–—]?\s*"
    r"((?:\+|00)?\s*(?:\(\s*\d{1,5}\s*\)|\d)[\d\s().\-–—/]{4,}\d"
    r"(?:\s*(?:ext\.?|extension|x)\s*\d{1,6})?)",
    re.IGNORECASE,
)

ABOUT_KEYWORDS = (
    "about",
    "about-us",
    "aboutus",
    "who-we-are",
    "our-company",
    "company-profile",
    "our-story",
    "من-نحن",
    "عن-الشركة",
    "من نحن",
    "عن الشركة",
)

CONTACT_KEYWORDS = (
    "contact",
    "contact-us",
    "contactus",
    "get-in-touch",
    "reach-us",
    "location",
    "our-offices",
    "support",
    "اتصل",
    "اتصل-بنا",
    "تواصل",
    "تواصل-معنا",
    "اتصل بنا",
    "تواصل معنا",
)

SOCIAL_DOMAINS = (
    "facebook.com",
    "fb.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "pinterest.com",
    "snapchat.com",
    "t.me",
    "telegram.me",
    "wa.me",
    "whatsapp.com",
)

ADDRESS_LABELS = (
    "address",
    "location",
    "head office",
    "headquarters",
    "office address",
    "registered office",
    "our office",
    "find us",
    "العنوان",
    "موقعنا",
    "الموقع",
    "المكتب الرئيسي",
)

INVALID_EMAIL_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "svg",
    "css",
    "js",
    "ico",
    "woff",
    "woff2",
    "ttf",
    "map",
}

PHONE_LABEL_WORDS = (
    "phone",
    "telephone",
    "tel",
    "mobile",
    "whatsapp",
    "contact number",
    "هاتف",
    "تلفون",
    "موبايل",
    "جوال",
    "واتساب",
)

ARABIC_DIGIT_TRANSLATION = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
    "01234567890123456789",
)


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = unescape(str(value))
    text = text.replace("\u200b", "").replace("\ufeff", "")
    return re.sub(r"\s+", " ", text).strip()


def normalize_start_url(url: str) -> str:
    url = clean_text(url)
    if not url:
        raise ValueError("URL is required")

    if not urlparse(url).scheme:
        url = "https://" + url

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Invalid URL")

    return normalize_page_url(url)


def normalize_page_url(url: str) -> str:
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
      path = path.rstrip("/")

    return parsed._replace(path=path, fragment="").geturl()


def normalized_host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    host = host.split("@")[-1]
    host = host.split(":")[0]

    if host.startswith("www."):
        host = host[4:]

    return host


def same_site(first_url: str, second_url: str) -> bool:
    return normalized_host(first_url) == normalized_host(second_url)


def unique_preserve_order(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()

    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)

    return result


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)

    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.35,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(("GET", "HEAD")),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_page(
    session: requests.Session,
    url: str,
) -> Optional[Tuple[str, BeautifulSoup]]:
    try:
        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if content_type and "html" not in content_type and "xhtml" not in content_type:
            return None

        response.encoding = response.apparent_encoding or response.encoding
        final_url = normalize_page_url(response.url)
        soup = BeautifulSoup(response.text, "html.parser")
        return final_url, soup

    except requests.RequestException:
        return None


# ---------------------------------------------------------------------------
# Related page discovery
# ---------------------------------------------------------------------------


def find_related_pages(
    soup: BeautifulSoup,
    base_url: str,
) -> List[Tuple[str, str]]:
    candidates: Dict[str, Tuple[int, str]] = {}

    def add_candidate(raw_url: str, page_type: str, priority: int) -> None:
        raw_url = clean_text(raw_url)
        if not raw_url:
            return

        lower_raw = raw_url.lower()
        if lower_raw.startswith(("mailto:", "tel:", "javascript:", "data:")):
            return

        full_url = normalize_page_url(urljoin(base_url, raw_url))
        parsed = urlparse(full_url)

        if parsed.scheme not in ("http", "https"):
            return

        if not same_site(base_url, full_url):
            return

        if full_url == normalize_page_url(base_url):
            return

        old_value = candidates.get(full_url)
        if old_value is None or priority < old_value[0]:
            candidates[full_url] = (priority, page_type)

    for link in soup.find_all("a", href=True):
        href = clean_text(link.get("href"))
        link_text = clean_text(link.get_text(" ", strip=True)).lower()
        searchable_text = f"{href.lower()} {link_text}"

        if any(keyword in searchable_text for keyword in CONTACT_KEYWORDS):
            add_candidate(href, "contact", 0)
        elif any(keyword in searchable_text for keyword in ABOUT_KEYWORDS):
            add_candidate(href, "about", 10)

    found_types = {page_type for _, page_type in candidates.values()}
    parsed_base = urlparse(base_url)
    root_url = f"{parsed_base.scheme}://{parsed_base.netloc}"

    if "contact" not in found_types:
        for index, path in enumerate(
            ("/contact",
                "/contact-us",
                "/contactus",
                "/get-in-touch",
                "/support",
                "/اتصل-بنا",
                "/تواصل-معنا",
            )
        ):
            add_candidate(urljoin(root_url, path), "contact", 20 + index)

    if "about" not in found_types:
        for index, path in enumerate(
            (
                "/about",
                "/about-us",
                "/aboutus",
                "/who-we-are",
                "/our-company",
                "/من-نحن",
            )
        ):
            add_candidate(urljoin(root_url, path), "about", 40 + index)

    ordered = sorted(
        candidates.items(),
        key=lambda item: (item[1][0], len(urlparse(item[0]).path)),
    )

    return [
        (url, page_type)
        for url, (_, page_type) in ordered[:MAX_EXTRA_PAGES]
    ]


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------


def get_meta_content(
    soup: BeautifulSoup,
    selectors: Sequence[Dict[str, str]],
) -> str:
    for attributes in selectors:
        tag = soup.find("meta", attrs=attributes)
        if tag and tag.get("content"):
            value = clean_text(tag.get("content"))
            if value:
                return value

    return ""


def extract_title(soup: BeautifulSoup) -> str:
    title = get_meta_content(
        soup,
        (
            {"property": "og:title"},
            {"name": "twitter:title"},
        ),
    )
    if title:
        return title

    if soup.title and soup.title.string:
        return clean_text(soup.title.string)

    heading = soup.find("h1")
    return clean_text(heading.get_text(" ", strip=True)) if heading else ""


def extract_name(soup: BeautifulSoup) -> str:
    name = get_meta_content(
        soup,
        (
            {"property": "og:site_name"},
            {"name": "application-name"},
        ),
    )
    return name or extract_title(soup)


def extract_description(soup: BeautifulSoup) -> str:
    return get_meta_content(
        soup,
        (
            {"name": "description"},
            {"property": "og:description"},
            {"name": "twitter:description"},
        ),
    )


def extract_keywords(soup: BeautifulSoup) -> List[str]:
    tag = soup.find(
        "meta",
        attrs={"name": re.compile(r"^keywords$", re.IGNORECASE)},
    )
    if not tag or not tag.get("content"):
        return []

    keywords = [
        clean_text(keyword)
        for keyword in str(tag.get("content", "")).split(",")
    ]
    return unique_preserve_order([keyword for keyword in keywords if keyword])


def extract_favicon(soup: BeautifulSoup, page_url: str) -> str:
    for selector in (
        'link[rel~="icon"]',
        'link[rel="shortcut icon"]',
        'link[rel="apple-touch-icon"]',
    ):
        tag = soup.select_one(selector)
        if tag and tag.get("href"):
            return urljoin(page_url, clean_text(tag.get("href")))

    parsed = urlparse(page_url)
    root_url = f"{parsed.scheme}://{parsed.netloc}"
    return urljoin(root_url, "/favicon.ico")


def extract_og_image(soup: BeautifulSoup, page_url: str) -> Optional[str]:
    image = get_meta_content(
        soup,
        (
            {"property": "og:image"},
            {"property": "og:image:url"},
            {"property": "og:image:secure_url"},
            {"name": "twitter:image"},
            {"name": "twitter:image:src"},
        ),
    )
    if image:
        return urljoin(page_url, image)

    ignored_words = (
        "favicon",
        "icon",
        "logo",
        "avatar",
        "flag",
        "loading",
        "spinner",
        "payment",
        "captcha",
        "pixel",
    )
    for image_tag in soup.find_all("img"):
        image_source = (
            image_tag.get("src")
            or image_tag.get("data-src")
            or image_tag.get("data-lazy-src")
            or image_tag.get("data-original")
        )
        image_source = clean_text(image_source)

        if not image_source:
            continue

        lower_source = image_source.lower()
        if any(word in lower_source for word in ignored_words):
            continue

        if image_source.startswith(("data:", "javascript:")):
            continue

        return urljoin(page_url, image_source)

    return None


# ---------------------------------------------------------------------------
# JSON-LD helpers
# ---------------------------------------------------------------------------


def iter_jsonld(soup: BeautifulSoup) -> Iterable[Any]:
    for script in soup.find_all("script", type="application/ld+json"):
        raw_json = script.string or script.get_text()
        if not raw_json or not raw_json.strip():
            continue

        raw_json = raw_json.strip()
        try:
            yield json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            # Some sites wrap JSON-LD in HTML comments or trailing semicolons.
            cleaned = re.sub(r"^\s*<!--|-->\s*$", "", raw_json).strip().rstrip(";")
            try:
                yield json.loads(cleaned)
            except (json.JSONDecodeError, TypeError):
                continue


def walk_json_values(data: Any) -> Iterable[Tuple[str, Any]]:
    if isinstance(data, list):
        for item in data:
            yield from walk_json_values(item)
        return

    if not isinstance(data, dict):
        return

    for key, value in data.items():
        yield str(key), value
        if isinstance(value, (dict, list)):
            yield from walk_json_values(value)


# ---------------------------------------------------------------------------
# Email extraction
# ---------------------------------------------------------------------------


def decode_cloudflare_email(encoded_value: Any) -> Optional[str]:
    if not encoded_value:
        return None

    try:
        encoded = str(encoded_value).strip()
        key = int(encoded[:2], 16)
        decoded_email = "".join(
            chr(int(encoded[index : index + 2], 16) ^ key)
            for index in range(2, len(encoded), 2)
        )
        decoded_email = decoded_email.strip().lower()
        return decoded_email or None
    except (ValueError, TypeError, IndexError):
        return None


def normalize_email(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = unquote(unescape(str(value))).strip()
    text = re.sub(r"^mailto:\s*", "", text, flags=re.IGNORECASE)
    text = text.split("?", 1)[0].split("#", 1)[0]
    text = text.replace("＠", "@").replace("﹫", "@").replace("。", ".")
    text = text.strip(" \t\r\n<>[](){}'\".,;:")

    match = EMAIL_REGEX.search(text)
    if not match:
        return None

    email = match.group(1).lower().strip(".")
    local_part, domain = email.rsplit("@", 1)

    if not local_part or not domain or ".." in email:
        return None

    extension = domain.rsplit(".", 1)[-1].lower()
    if extension in INVALID_EMAIL_EXTENSIONS:
        return None

    if domain.startswith(".") or domain.endswith("."):
        return None

    return email


def extract_emails(soup: BeautifulSoup) -> List[str]:
    found: Dict[str, Tuple[int, str]] = {}

    def add_email(value: Any, score: int) -> None:
        if not value:
            return

        text = unquote(unescape(str(value)))

        for match in EMAIL_REGEX.findall(text):
            email = normalize_email(match)
            if not email:
                continue

            old = found.get(email)
            if old is None or score < old[0]:
                found[email] = (score, email)
                for local_part, domain, extension in OBFUSCATED_EMAIL_REGEX.findall(text):  
                   email = normalize_email(f"{local_part}@{domain}.{extension}")

            if not email:
                continue

            old = found.get(email)
            if old is None or score < old[0]:
                found[email] = (score, email)

    # 1) Explicit mailto links are the most reliable source.
    for link in soup.select('a[href^="mailto:"]'):
        add_email(link.get("href"), 0)

    # 2) Cloudflare-protected emails.
    for element in soup.select("[data-cfemail]"):
        add_email(decode_cloudflare_email(element.get("data-cfemail")), 0)

    for link in soup.select('a[href*="/cdn-cgi/l/email-protection"]'):
        href = clean_text(link.get("href"))
        if "#" in href:
            add_email(decode_cloudflare_email(href.split("#", 1)[1]), 0)

    # 3) Common meta and microdata attributes.
    for tag in soup.select(
        '[itemprop="email"], [data-email], [data-mail], meta[name="email"], meta[property="email"]'
    ):
        add_email(
            tag.get("content")
            or tag.get("href")
            or tag.get("data-email")
            or tag.get("data-mail")
            or tag.get_text(" ", strip=True),
            1,
        )

    # 4) JSON-LD fields such as email/contactPoint.
    for data in iter_jsonld(soup):
        for key, value in walk_json_values(data):
            if key.lower() in {"email", "mail", "contactemail"}:
                if isinstance(value, list):
                    for item in value:
                        add_email(item, 1)
                else:
                    add_email(value, 1)

    # 5) Visible text. This also catches plain-text emails in the footer.
    page_text = soup.get_text(" ", strip=True)
    add_email(page_text, 2)

    # 6) Raw HTML and JavaScript strings, including escaped forms.
    page_html = str(soup)
    add_email(page_html, 3)
    add_email(page_html.replace("\\u0040", "@").replace("\\x40", "@"), 3)

    preferred_prefixes = (
        "info",
        "contact",
        "hello",
        "support",
        "sales",
        "office",
        "admin",
        "enquiry",
        "inquiry",
    )

    def email_score(item: Tuple[int, str]) -> Tuple[int, int, int]:
        source_score, email = item
        local_part = email.split("@", 1)[0].lower()
        rank = next(
            (
                index
                for index, prefix in enumerate(preferred_prefixes)
                if local_part.startswith(prefix)
            ),
            len(preferred_prefixes),
        )
        return source_score, rank, len(email)

    ordered = sorted(found.values(), key=email_score)
    return [email for _, email in ordered[:MAX_RESULT_ITEMS]]


# ---------------------------------------------------------------------------
# Phone extraction
# ---------------------------------------------------------------------------


def normalize_phone_characters(value: str) -> str:
    return (
        value.translate(ARABIC_DIGIT_TRANSLATION)
        .replace("＋", "+")
        .replace("﹢", "+")
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .replace(" ", " ")
    )


def clean_phone(value: Any) -> Optional[str]:
    if not value:
        return None

    text = normalize_phone_characters(unquote(unescape(str(value)))).strip()
    text = re.sub(r"^\s*tel:\s*", "", text, flags=re.IGNORECASE)
    text = text.split("?", 1)[0].split("#", 1)[0]

    text = re.sub(
        r"^(?:phone|telephone|tel\.?|mobile|mob\.?|whatsapp|contact\s*(?:number|no\.?)?|"
        r"هاتف|الهاتف|تلفون|موبايل|جوال|واتساب)\s*[:：\-–—]?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\s+", " ", text)
    text = text.strip(" \t\r\n,;:|<>[]{}\"")# Keep the original formatting (+, 00, spaces, parentheses and dashes),
    # but reject impossible or clearly fake values.
    extension_match = re.search(
        r"\s*(?:ext\.?|extension|x)\s*(\d{1,6})\s*$",
        text,
        flags=re.IGNORECASE,
    )
    main_text = text[: extension_match.start()] if extension_match else text
    digits = re.sub(r"\D", "", main_text)

    if not 7 <= len(digits) <= 15:
        return None

    if len(set(digits)) == 1:
        return None

    # Reject typical dates and timestamps when they are not marked as phone data.
    if re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", main_text):
        return None

    return text


def phone_key(phone: str) -> str:
    normalized = normalize_phone_characters(phone)
    main = re.split(r"\s*(?:ext\.?|extension|x)\s*", normalized, maxsplit=1, flags=re.IGNORECASE)[0]
    digits = re.sub(r"\D", "", main)

    # 00 and + are equivalent for deduplication, but the displayed value remains unchanged.
    if main.strip().startswith("00") and len(digits) > 2:
        digits = digits[2:]

    return digits


def extract_phone_candidates(text: str) -> List[str]:
    text = normalize_phone_characters(unquote(unescape(text)))
    return [match.group(0) for match in PHONE_REGEX.finditer(text)]


def extract_phones(soup: BeautifulSoup) -> List[str]:
    found: Dict[str, Tuple[int, str]] = {}

    def add_phone(value: Any, score: int, allow_multiple: bool = True) -> None:
        if not value:
            return

        raw_text = normalize_phone_characters(unquote(unescape(str(value))))
        candidates = extract_phone_candidates(raw_text) if allow_multiple else [raw_text]

        if not candidates and not allow_multiple:
            candidates = [raw_text]

        for candidate in candidates:
            phone = clean_phone(candidate)
            if not phone:
                continue

            key = phone_key(phone)
            if not key:
                continue

            old = found.get(key)
            if old is None or score < old[0] or (
                score == old[0] and len(phone) > len(old[1])
            ):
                found[key] = (score, phone)

    # 1) Explicit tel: links preserve prefixes and symbols exactly as written.
    for link in soup.select('a[href^="tel:"]'):
        add_phone(link.get("href"), 0, allow_multiple=False)

    # 2) WhatsApp URLs often contain a phone number even when no tel: link exists.
    for link in soup.find_all("a", href=True):
        href = clean_text(link.get("href"))
        lower_href = href.lower()

        if "wa.me/" in lower_href:
            add_phone(lower_href.split("wa.me/", 1)[1].split("?", 1)[0], 1, False)
        elif "whatsapp.com" in lower_href:
            parsed = urlparse(urljoin("https://example.invalid", href))
            query = parse_qs(parsed.query)
            for value in query.get("phone", []):
                add_phone(value, 1, False)

    # 3) Microdata, data attributes and meta tags.
    for tag in soup.select(
        '[itemprop="telephone"], [itemprop="phone"], [data-phone], [data-tel], '
        'meta[name="telephone"], meta[name="phone"], meta[property="telephone"]'
    ):
        add_phone(
            tag.get("content")
            or tag.get("href")
            or tag.get("data-phone")
            or tag.get("data-tel")
            or tag.get_text(" ", strip=True),
            1,
            True,
        )

    # 4) JSON-LD fields.
    for data in iter_jsonld(soup):
        for key, value in walk_json_values(data):
            if key.lower() in {
                "telephone",
                "phone",
                "phonenumber",
                "contactnumber",
                "mobile",
            }:
                if isinstance(value, list):
                    for item in value:
                        add_phone(item, 1, True)
                else:
                    add_phone(value, 1, True)

    page_text = normalize_phone_characters(soup.get_text(" ", strip=True))# 5) Numbers explicitly labeled as phone/mobile/WhatsApp.
    for match in LABELED_PHONE_REGEX.finditer(page_text):
        add_phone(match.group(1), 2, False)

    # 6) Generic visible candidates. Require either a prefix or formatting so that
    # years, IDs and counters are less likely to be selected as phone numbers.
    for candidate in extract_phone_candidates(page_text):
        compact = candidate.strip()
        has_phone_formatting = bool(re.search(r"[+()\-\s]", compact))
        starts_international = compact.startswith(("+", "00"))

        if has_phone_formatting or starts_international:
            add_phone(compact, 3, False)

    # 7) Search raw HTML/JavaScript for phone-like values and labeled fields.
    page_html = normalize_phone_characters(str(soup))

    for match in re.finditer(
        r"[\"'](?:telephone|phone|mobile|whatsapp|contactNumber)[\"']\s*:\s*[\"']([^\"']+)[\"']",
        page_html,
        flags=re.IGNORECASE,
    ):
        add_phone(match.group(1), 2, True)

    for match in LABELED_PHONE_REGEX.finditer(page_html):
        add_phone(match.group(1), 3, False)

    def phone_score(item: Tuple[int, str]) -> Tuple[int, int, int]:
        source_score, phone = item
        stripped = phone.strip()
        international_rank = 0 if stripped.startswith(("+", "00")) else 1
        return source_score, international_rank, -len(re.sub(r"\D", "", phone))

    ordered = sorted(found.values(), key=phone_score)
    return [phone for _, phone in ordered[:MAX_RESULT_ITEMS]]


# ---------------------------------------------------------------------------
# Social links and addresses
# ---------------------------------------------------------------------------


def normalize_social_url(raw_url, page_url):
    if not raw_url:
        return None

    value = unescape(str(raw_url)).strip()
    value = value.strip("\"'<>[]()")
    value = value.replace("\\/", "/")
    value = unquote(value)

    if not value:
        return None

    lower_value = value.lower()

    if lower_value.startswith(
        (
            "mailto:",
            "tel:",
            "javascript:",
            "data:",
            "#",
        )
    ):
        return None

    # روابط تبدأ بـ //facebook.com
    if value.startswith("//"):
        value = "https:" + value

    # روابط اجتماعية بدون https
    elif (
        not urlparse(value).scheme
        and any(domain in lower_value for domain in SOCIAL_DOMAINS)
    ):
        value = "https://" + value.lstrip("/")

    else:
        value = urljoin(page_url, value)

    parsed = urlparse(value)

    # معالجة روابط التحويل مثل:
    # site.com/redirect?url=https://facebook.com/account
    query_parameters = parse_qs(parsed.query)

    redirect_keys = (
        "url",
        "u",
        "q",
        "target",
        "redirect",
        "redirect_url",
        "next",
        "continue",
    )

    for key in redirect_keys:
        for redirected_value in query_parameters.get(key, []):
            redirected_value = unquote(redirected_value)
            redirected_value = redirected_value.replace("\\/", "/")

            if any(
                domain in redirected_value.lower()
                for domain in SOCIAL_DOMAINS
            ):
                return normalize_social_url(
                    redirected_value,
                    page_url,
                )

    host = parsed.netloc.lower()
    host = host.split("@")[-1]
    host = host.split(":")[0]

    if host.startswith("www."):
        host = host[4:]

    is_social_domain = any(
        host == domain or host.endswith("." + domain)
        for domain in SOCIAL_DOMAINS
    )

    if not is_social_domain:
        return None

    lower_path = (parsed.path or "").lower()

    # استبعاد روابط المشاركة، لأنها ليست حسابات الموقع
    share_markers = (
        "/share",
        "/sharer",
        "/sharing",
        "/intent/tweet",
        "/intent/post",
        "/dialog/share",
        "/pin/create",
        "/send",
    )

    if any(marker in lower_path for marker in share_markers):
      return None

    # إزالة fragment مثل #section
    cleaned_url = parsed._replace(fragment="").geturl()

    # إزالة الرموز التي قد تلتصق بالرابط داخل JavaScript
    cleaned_url = cleaned_url.rstrip(
        ".,;:!?)]}'\""
    )

    return cleaned_url


def extract_social_links(soup, page_url):
    social_links = []
    seen = set()

    def add_social_link(raw_value):
        if raw_value is None:
            return

        if isinstance(raw_value, (list, tuple, set)):
            for item in raw_value:
                add_social_link(item)
            return

        normalized_url = normalize_social_url(
            raw_value,
            page_url,
        )

        if not normalized_url:
            return

        comparison_key = normalized_url.lower().rstrip("/")

        if comparison_key not in seen:
            seen.add(comparison_key)
            social_links.append(normalized_url)

    # 1. البحث في جميع الخصائص المحتملة
    social_attributes = (
        "href",
        "src",
        "content",
        "data-href",
        "data-url",
        "data-link",
        "data-social",
        "data-share-url",
        "data-clipboard-text",
    )

    for tag in soup.find_all(True):
        for attribute in social_attributes:
            add_social_link(tag.get(attribute))

    # 2. البحث داخل JSON-LD، خصوصًا sameAs
    def search_json_data(data):
        if isinstance(data, dict):
            for key, value in data.items():
                lower_key = str(key).lower()

                if lower_key in (
                    "sameas",
                    "url",
                    "social",
                    "sociallinks",
                    "social_links",
                ):
                    add_social_link(value)

                search_json_data(value)

        elif isinstance(data, list):
            for item in data:
                search_json_data(item)

    for script in soup.find_all(
        "script",
        type="application/ld+json",
    ):
        raw_json = script.string or script.get_text()

        if not raw_json or not raw_json.strip():
            continue

        try:
            json_data = json.loads(raw_json)
            search_json_data(json_data)

        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    # 3. البحث داخل HTML وJavaScript الخام
    page_html = str(soup).replace("\\/", "/")

    domains_pattern = "|".join(
        re.escape(domain)
        for domain in SOCIAL_DOMAINS
    )

    social_pattern = re.compile(
        rf"""
        (?:
            https?:
        )?
        //
        (?:
            www\.
        )?
        (?:
            {domains_pattern}
        )
        [^\s"'<>\\]*
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    for match in social_pattern.finditer(page_html):
        add_social_link(match.group(0))

    # 4. البحث عن نطاقات مكتوبة بدون http
    bare_social_pattern = re.compile(
        rf"""
        (?<![\w@])
        (?:
            www\.
        )?
        (?:
            {domains_pattern}
        )
        /
        [^\s"'<>\\]+
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    for match in bare_social_pattern.finditer(page_html):
        add_social_link(match.group(0))

    return social_links


def flatten_postal_address(value: Any) -> str:
    if isinstance(value, str):
        return clean_text(value)

    if not isinstance(value, dict):
        return ""

    parts: List[str] = []
    for key in (
        "streetAddress",
        "addressLocality",
        "addressRegion",
        "postalCode",
        "addressCountry",
    ):
        part = clean_text(value.get(key, ""))
        if part:
            parts.append(part)

    return ", ".join(dict.fromkeys(parts))


def collect_jsonld_addresses(data: Any, addresses: List[str]) -> None:
    if isinstance(data, list):
        for item in data:
            collect_jsonld_addresses(item, addresses)
        return

    if not isinstance(data, dict):
        return

    if data.get("@type") == "PostalAddress":
        address = flatten_postal_address(data)
        if address:
            addresses.append(address)

    if "address" in data:
        address = flatten_postal_address(data.get("address"))
        if address:
            addresses.append(address)

    for value in data.values():
        if isinstance(value, (dict, list)):
            collect_jsonld_addresses(value, addresses)


def plausible_address(value: str) -> bool:
    value = clean_text(value)
    if len(value) < 8 or len(value) > 350:
        return False

    digits = sum(character.isdigit() for character in value)
    letters = sum(character.isalpha() for character in value)
    return letters >= 4 and (digits >= 1 or "," in value or len(value.split()) >= 4)


def extract_addresses(soup: BeautifulSoup) -> List[str]:
    candidates: List[Tuple[int, str]] = []

    def add_address(raw_value: Any, score: int) -> None:
        value = clean_text(raw_value)
        if plausible_address(value):
            candidates.append((score, value))

    for tag in soup.find_all("address"):
        add_address(tag.get_text(" ", strip=True), 0)

    for tag in soup.find_all(True):
        tag_id = clean_text(tag.get("id")).lower()
        class_names = " ".join(tag.get("class", [])).lower()
        itemprop = clean_text(tag.get("itemprop")).lower()
        searchable = f"{tag_id} {class_names} {itemprop}"

        if "address" in searchable or "location" in searchable:
            add_address(tag.get_text(" ", strip=True), 1)

    for data in iter_jsonld(soup):
        jsonld_addresses: List[str] = []
        collect_jsonld_addresses(data, jsonld_addresses)
        for address in jsonld_addresses:
            add_address(address, 0)

    page_text = soup.get_text("\n", strip=True)
    lines = [clean_text(line) for line in page_text.splitlines() if clean_text(line)]

    for index, line in enumerate(lines):
        lower_line = line.lower()
        if not any(label in lower_line for label in ADDRESS_LABELS):
            continue

        if ":" in line:
            add_address(line.split(":", 1)[1], 2)

        if index + 1 < len(lines):
            add_address(lines[index + 1], 3)

    addresses: List[str] = []
    seen = set()

    for _, value in sorted(candidates, key=lambda item: (item[0], -len(item[1]))):
        key = value.lower()
        if key not in seen:
            seen.add(key)
            addresses.append(value)

    return addresses[:MAX_RESULT_ITEMS]


# ---------------------------------------------------------------------------
# Main scraping flow
# ---------------------------------------------------------------------------


def scrape_url(raw_url: str) -> Dict[str, Any]:
    start_url = normalize_start_url(raw_url)

    with make_session() as session:
        home_result = fetch_page(session, start_url)

        # Some sites reject HTTPS but still support HTTP.
        if home_result is None and start_url.startswith("https://"):
            fallback_url = "http://" + start_url[len("https://") :]
            home_result = fetch_page(session, fallback_url)

        if home_result is None:
            return {
                "success": False,
                "error": "Could not open the requested website",
                "url": start_url,
                "phone": None,
                "email": None,
                "phones": [],
                "emails": [],
            }

        home_url, home_soup = home_result
        pages: List[Dict[str, Any]] = [
            {
                "type": "home",
                "url": home_url,
                "soup": home_soup,
            }
        ]
        visited_pages = {home_url}

        for candidate_url, page_type in find_related_pages(home_soup, home_url):
            if candidate_url in visited_pages:
                continue

            page_result = fetch_page(session, candidate_url)
            if page_result is None:
                continue

            final_page_url, page_soup = page_result
            if final_page_url in visited_pages:
                continue

            if not same_site(home_url, final_page_url):
                continue

            visited_pages.add(final_page_url)
            pages.append(
                {
                    "type": page_type,
                    "url": final_page_url,
                    "soup": page_soup,
                }
            )

        page_priority = {"contact": 0, "about": 1, "home": 2}
        prioritized_pages = sorted(
            pages,
            key=lambda page: page_priority.get(page["type"], 3),
        )

        all_emails: List[str] = []
        all_phones: List[str] = []
        all_addresses: List[str] = []
        all_social_links: List[str] = []

        seen_email = set()
        seen_phone = set()
        seen_address = set()
        seen_social = set()
        for page in prioritized_pages:
            page_url = page["url"]
            page_soup = page["soup"]

            for found_email in extract_emails(page_soup):
                key = found_email.lower()
                if key not in seen_email:
                    seen_email.add(key)
                    all_emails.append(found_email)

            for found_phone in extract_phones(page_soup):
                key = phone_key(found_phone)
                if key not in seen_phone:
                    seen_phone.add(key)
                    all_phones.append(found_phone)

            for found_address in extract_addresses(page_soup):
                key = found_address.lower()
                if key not in seen_address:
                    seen_address.add(key)
                    all_addresses.append(found_address)

            for found_link in extract_social_links(page_soup, page_url):
                key = found_link.lower()
                if key not in seen_social:
                    seen_social.add(key)
                    all_social_links.append(found_link)

        email = all_emails[0] if all_emails else None
        phone = all_phones[0] if all_phones else None
        address = all_addresses[0] if all_addresses else None

        return {
            "success": True,
            "url": home_url,
            "name": extract_name(home_soup) or None,
            "title": extract_title(home_soup) or None,
            "description": extract_description(home_soup) or None,
            "address": address,
            "og_image": extract_og_image(home_soup, home_url),
            "keywords": extract_keywords(home_soup),
            "favicon": extract_favicon(home_soup, home_url),
            "social_links": all_social_links,
            "phone": phone,
            "email": email,
            # Keep every detected value as well. Node.js can use the first value
            # through phone/email or display the complete arrays when needed.
            "phones": all_phones,
            "emails": all_emails,
            "addresses": all_addresses,
            "pages_scraped": [page["url"] for page in pages],
        }


def main() -> None:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")

        if len(sys.argv) < 2:
            result: Dict[str, Any] = {
                "success": False,
                "error": "Usage: python scraper.py <url>",
                "phone": None,
                "email": None,
                "phones": [],
                "emails": [],
            }
        else:
            result = scrape_url(sys.argv[1])

    except Exception as error:  # Keep stdout as valid JSON for the Node.js process.
        result = {
            "success": False,
            "error": str(error),
            "phone": None,
            "email": None,
            "phones": [],
            "emails": [],
        }

    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()


if __name__ == "__main__":
     main()