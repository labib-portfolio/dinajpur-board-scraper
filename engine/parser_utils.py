import json
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin


def parse_html_to_json(
    html_content: str,
    url: Optional[str] = None,
    status_code: Optional[int] = None,
    include_html: bool = False
) -> Dict[str, Any]:
    """
    Comprehensively parses HTML content into a rich, structured JSON dictionary.
    Extracts:
      - page metadata (title, meta tags, url, status code)
      - tables (converted to structured records)
      - key-value definitions (from <dl>, strong/b labels, badges)
      - headings and content sections
      - bullet and numbered lists
      - links and media references
      - full text content
    """
    # Check if the content is already a JSON response
    trimmed = html_content.strip()
    if (trimmed.startswith('{') and trimmed.endswith('}')) or (trimmed.startswith('[') and trimmed.endswith(']')):
        try:
            parsed_json = json.loads(trimmed)
            return {
                "source_type": "json_response",
                "url": url,
                "status_code": status_code,
                "data": parsed_json
            }
        except Exception:
            pass

    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Metadata
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_desc = ""
    desc_tag = soup.find('meta', attrs={'name': re.compile(r'description', re.I)}) or soup.find('meta', attrs={'property': 'og:description'})
    if desc_tag:
        meta_desc = desc_tag.get('content', '').strip()

    # 2. Alerts / Messages / Banners
    alerts = []
    alert_elements = soup.select('.alert, .message, .notification, .toast, .banner, .badge, [role="alert"]')
    for el in alert_elements:
        text = el.get_text(separator=' ', strip=True)
        if text and text not in alerts and len(text) < 300:
            alerts.append(text)

    # 3. Extract All Tables
    tables = []
    for idx, table in enumerate(soup.find_all('table')):
        table_data = _parse_table(table, idx)
        if table_data.get("rows") or table_data.get("headers"):
            tables.append(table_data)

    # 4. Extract Key-Value Pairs
    key_values = _parse_key_values(soup)

    # 5. Extract Headings and Content Sections
    sections = []
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        h_text = heading.get_text(strip=True)
        p_texts = []
        sibling = heading.find_next_sibling()
        while sibling and sibling.name in ['p', 'ul', 'ol', 'div', 'blockquote', 'table'] and sibling.name not in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            if sibling.name in ['ul', 'ol']:
                items = [li.get_text(strip=True) for li in sibling.find_all('li') if li.get_text(strip=True)]
                if items:
                    p_texts.append("\n".join(f"- {i}" for i in items))
            elif sibling.name != 'table':
                txt = sibling.get_text(strip=True)
                if txt and len(txt) > 2:
                    p_texts.append(txt)
            sibling = sibling.find_next_sibling()

        sections.append({
            "heading": h_text,
            "level": heading.name,
            "content": p_texts
        })

    # 6. Extract Lists
    lists = []
    for list_el in soup.find_all(['ul', 'ol']):
        # Skip if parent is already a list
        if list_el.find_parent(['ul', 'ol']):
            continue
        items = [li.get_text(strip=True) for li in list_el.find_all('li') if li.get_text(strip=True)]
        if items and len(items) >= 2:
            lists.append({
                "type": "ordered" if list_el.name == 'ol' else "unordered",
                "item_count": len(items),
                "items": items
            })

    # 7. Extract Links
    links = []
    for a in soup.find_all('a', href=True):
        href = a.get('href', '').strip()
        link_text = a.get_text(strip=True)
        if href and not href.startswith('#') and not href.startswith('javascript:'):
            full_link = urljoin(url or '', href)
            links.append({
                "text": link_text or href,
                "url": full_link
            })

    # 8. Clean Full Text Extraction
    soup_clean = BeautifulSoup(html_content, 'html.parser')
    for s in soup_clean(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        s.decompose()
    clean_text = soup_clean.get_text(separator='\n', strip=True)
    text_lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

    result = {
        "status_code": status_code,
        "url": url,
        "title": title,
        "description": meta_desc,
        "alerts": alerts,
        "tables": tables,
        "key_value_data": key_values,
        "sections": sections,
        "lists": lists,
        "links": links[:50],  # first 50 links
        "full_text_summary": text_lines,
    }

    if include_html:
        result["raw_html"] = html_content

    return result


def _parse_table(table: Tag, table_idx: int) -> Dict[str, Any]:
    """Convert an HTML <table> into JSON table structure with headers and rows."""
    headers = []
    thead = table.find('thead')
    if thead:
        headers = [th.get_text(strip=True) for th in thead.find_all(['th', 'td'])]

    rows_data = []
    tbody = table.find('tbody') or table
    tr_list = tbody.find_all('tr')

    for tr_idx, tr in enumerate(tr_list):
        cells = tr.find_all(['td', 'th'])
        cell_texts = [c.get_text(strip=True) for c in cells]

        # Detect headers from the first row if <thead> is not used
        if not headers and tr_idx == 0 and any(c.name == 'th' for c in cells):
            headers = cell_texts
            continue

        if not cell_texts:
            continue

        if headers and len(headers) == len(cell_texts):
            row_dict = {headers[i] or f"col_{i+1}": cell_texts[i] for i in range(len(cell_texts))}
            rows_data.append(row_dict)
        else:
            row_dict = {f"column_{i+1}": cell_texts[i] for i in range(len(cell_texts))}
            rows_data.append(row_dict)

    table_id = table.get('id', '')
    table_class = " ".join(table.get('class', [])) if isinstance(table.get('class'), list) else str(table.get('class', ''))

    return {
        "table_index": table_idx + 1,
        "table_id": table_id,
        "table_class": table_class,
        "headers": headers,
        "row_count": len(rows_data),
        "rows": rows_data
    }


def _parse_key_values(soup: BeautifulSoup) -> Dict[str, str]:
    """Extract key-value structured data from tables (like bio tables), <dl>, labels, or formatted spans."""
    data = {}

    # Extract from key-value tables (e.g. 2-column or 4-column bio/info tables)
    for table in soup.find_all('table'):
        for tr in table.find_all('tr'):
            cells = [c.get_text(strip=True) for c in tr.find_all(['td', 'th']) if c.get_text(strip=True)]
            if len(cells) == 2:
                k, v = cells[0].rstrip(':').strip(), cells[1].strip()
                if k and v and len(k) < 60:
                    data[k] = v
            elif len(cells) == 4:
                k1, v1 = cells[0].rstrip(':').strip(), cells[1].strip()
                k2, v2 = cells[2].rstrip(':').strip(), cells[3].strip()
                if k1 and v1 and len(k1) < 60:
                    data[k1] = v1
                if k2 and v2 and len(k2) < 60:
                    data[k2] = v2

    # Check <dl><dt>Key</dt><dd>Value</dd></dl>
    for dl in soup.find_all('dl'):
        dts = dl.find_all('dt')
        dds = dl.find_all('dd')
        for dt, dd in zip(dts, dds):
            k = dt.get_text(strip=True).rstrip(':')
            v = dd.get_text(strip=True)
            if k and k not in data:
                data[k] = v

    # Check <strong>Key:</strong> Value patterns
    for strong in soup.find_all(['strong', 'b', 'label', 'th']):
        key_text = strong.get_text(strip=True)
        if key_text.endswith(':') or len(key_text.split()) <= 4:
            clean_k = key_text.rstrip(':').strip()
            parent = strong.parent
            if parent:
                parent_text = parent.get_text(separator=' ', strip=True)
                if parent_text.startswith(key_text):
                    val = parent_text[len(key_text):].strip()
                    if val and clean_k and clean_k not in data and len(clean_k) < 60:
                        data[clean_k] = val

    return data
