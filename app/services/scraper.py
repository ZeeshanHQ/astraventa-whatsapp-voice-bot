import logging
import re
from typing import Dict, Any, Optional
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("scraper_service")

async def scrape_website_summary(url: str, timeout: float = 6.0) -> Dict[str, Any]:
    """
    Rapidly scrapes a client's website URL to extract business context:
    - Business title
    - Meta description
    - Services & Key offerings
    - Phone number & address hints
    Returns clean concise text for dynamic prompt injection.
    """
    if not url or not url.strip():
        return {"success": False, "summary": "", "title": ""}

    target_url = url.strip()
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = f"https://{target_url}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=False) as client:
            resp = await client.get(target_url, headers=headers)
            if resp.status_code >= 400:
                logger.warning(f"Scraper received status {resp.status_code} for {target_url}")
                return {"success": False, "summary": "", "title": ""}

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            # Remove noise scripts, styles, navigations, svgs
            for tag in soup(["script", "style", "noscript", "svg", "footer", "nav"]):
                tag.decompose()

            # Extract Title
            title = ""
            if soup.title and soup.title.string:
                title = soup.title.string.strip()

            # Extract Meta Description
            meta_desc = ""
            meta_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag["content"].strip()

            # Extract Main Headings & Key Paragraphs
            headings = []
            for h in soup.find_all(["h1", "h2", "h3"])[:8]:
                text = h.get_text(strip=True)
                if text and len(text) > 4:
                    headings.append(text)

            paragraphs = []
            for p in soup.find_all("p")[:10]:
                text = p.get_text(strip=True)
                if text and len(text) > 25:
                    paragraphs.append(text)

            # Look for phone number
            phone_match = re.findall(r'(\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', html)
            detected_phone = phone_match[0] if phone_match else ""

            # Build condensed summary
            summary_parts = []
            if title:
                summary_parts.append(f"Business: {title}")
            if meta_desc:
                summary_parts.append(f"Overview: {meta_desc}")
            if headings:
                summary_parts.append(f"Key Offerings: {', '.join(headings[:5])}")
            if paragraphs:
                summary_parts.append(f"About: {' '.join(paragraphs[:3])}")
            if detected_phone:
                summary_parts.append(f"Contact Phone: {detected_phone}")

            full_summary = "\n".join(summary_parts)
            # Cap at 1500 chars to ensure minimal token consumption & ultra-fast LLM prompt processing
            truncated_summary = full_summary[:1500].strip()

            return {
                "success": True,
                "title": title,
                "summary": truncated_summary,
                "phone": detected_phone,
            }

    except Exception as exc:
        logger.warning(f"Fast scraper failed for {target_url}: {exc}")
        return {"success": False, "summary": "", "title": ""}
