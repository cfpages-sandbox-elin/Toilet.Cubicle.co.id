#!/usr/bin/env python3
"""High-Efficiency Heuristic Image Alt, 80/20 Internal Linking, & Robots.txt Engine.

Features:
- Standardizes robots.txt across commercial sites (Disallow /cdn-cgi/ to prevent Cloudflare 404s).
- Isolates Short.io tracker subdomains (track.*, link.*, klik.*) with Disallow: /.
- Infers page context from permalink / filename in < 0.1ms per file (zero DOM overhead).
- Wraps unlinked content images with internal links weighted 80% to Tier-1 high-value cities.
- Injects descriptive Indonesian alt attributes while preserving HTML byte integrity.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Tier-1 Indonesian Commercial Powerhouse Cities (~20% locations, ~80% revenue)
TIER1_CITIES: Set[str] = {
    # Jabodetabek Megapolitan
    "jakarta",
    "jakarta-pusat",
    "jakarta-selatan",
    "jakarta-barat",
    "jakarta-timur",
    "jakarta-utara",
    "bogor",
    "depok",
    "tangerang",
    "tangerang-selatan",
    "bekasi",
    # Java Economic Hubs
    "surabaya",
    "bandung",
    "semarang",
    "solo",
    "surakarta",
    "malang",
    "sidoarjo",
    "cirebon",
    "yogyakarta",
    "sleman",
    # Major Outer-Island Commercial Hubs
    "medan",
    "makassar",
    "denpasar",
    "badung",
    "palembang",
    "balikpapan",
    "samarinda",
    "batam",
    "pekanbaru",
    "bandar-lampung",
}

UTILITY_PAGES: Set[str] = {
    "index.html",
    "404.html",
    "about.html",
    "contact.html",
    "privacy-policy.html",
    "terms.html",
    "disclaimer.html",
    "sitemap.html",
}

TRACKER_PREFIXES: Tuple[str, ...] = ("track.", "link.", "klik.")


def is_tracker_domain(domain_or_repo: str) -> bool:
    clean = domain_or_repo.lower().strip()
    return any(clean.startswith(prefix) for prefix in TRACKER_PREFIXES)


def detect_domain(root: Path, repo_name: Optional[str] = None) -> str:
    # 1. CNAME file
    cname_file = root / "CNAME"
    if cname_file.is_file():
        domain = cname_file.read_text(encoding="utf-8", errors="ignore").strip().splitlines()[0]
        if domain:
            return domain

    # 2. Canonical tag in index.html or first HTML
    for html_file in root.glob("*.html"):
        try:
            head = html_file.read_text(encoding="utf-8", errors="ignore")[:4000]
            m = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']https?://([^/\'"]+)', head, re.I)
            if m:
                return m.group(1).lower()
        except Exception:
            continue

    # 3. Fallback to repo name or folder name
    name = repo_name or root.name
    return name.lower()


def ensure_robots_txt(root: Path, domain: str) -> Tuple[bool, str]:
    robots_path = root / "robots.txt"
    is_tracker = is_tracker_domain(domain) or is_tracker_domain(root.name)

    if is_tracker:
        expected = "User-agent: *\nDisallow: /\n"
    else:
        sitemap_name = "sitemap-complete.xml" if (root / "sitemap-complete.xml").is_file() else "sitemap.xml"
        expected = f"User-agent: *\nAllow: /\nDisallow: /cdn-cgi/\n\nSitemap: https://{domain}/{sitemap_name}\n"

    if not robots_path.is_file():
        robots_path.write_text(expected, encoding="utf-8")
        return True, "created"

    current = robots_path.read_text(encoding="utf-8", errors="ignore")
    if is_tracker:
        if "Disallow: /" in current and "Allow: /" not in current:
            return False, "already_tracker_clean"
        robots_path.write_text(expected, encoding="utf-8")
        return True, "overwritten_tracker"
    else:
        if "Disallow: /cdn-cgi/" in current:
            return False, "already_has_cdn_cgi"
        # Append Disallow: /cdn-cgi/ under User-agent: *
        if "User-agent: *" in current:
            updated = re.sub(r"(User-agent:\s*\*[^\n]*\n)", r"\1Disallow: /cdn-cgi/\n", current, count=1, flags=re.I)
        else:
            updated = f"User-agent: *\nDisallow: /cdn-cgi/\n\n{current}"
        robots_path.write_text(updated, encoding="utf-8")
        return True, "appended_cdn_cgi"


def clean_slug_to_title(slug: str) -> str:
    tokens = slug.replace("_", "-").split("-")
    cleaned = [t.capitalize() for t in tokens if t and not t.isdigit()]
    return " ".join(cleaned)


def extract_image_keywords(src: str) -> str:
    filename = os.path.basename(urllib.parse.urlsplit(src).path)
    base, _ = os.path.splitext(filename)
    base = urllib.parse.unquote(base)
    tokens = re.findall(r"[a-zA-Z]+", base)
    stop = {
        "wp", "content", "uploads", "img", "image", "dsc", "photo",
        "s", "jpg", "jpeg", "png", "webp", "gif", "large", "thumb"
    }
    meaningful = [t.capitalize() for t in tokens if len(t) > 2 and t.lower() not in stop]
    return " ".join(meaningful[:2])


def detect_common_product_prefix(filenames: List[str]) -> str:
    candidates: Dict[str, int] = {}
    for f in filenames:
        base = f[:-5] if f.endswith(".html") else f
        parts = base.split("-")
        for i in range(1, min(len(parts), 5)):
            prefix = "-".join(parts[:i])
            candidates[prefix] = candidates.get(prefix, 0) + 1
    if not candidates:
        return "Layanan"
    sorted_prefixes = sorted(candidates.items(), key=lambda x: (-x[1], -len(x[0])))
    best_prefix, best_count = sorted_prefixes[0]
    return best_prefix if best_count >= max(2, len(filenames) * 0.3) else ""


def parse_page_context(filename: str, common_prefix: str) -> Tuple[str, str]:
    base = filename[:-5] if filename.endswith(".html") else filename
    if common_prefix and base.startswith(common_prefix + "-"):
        city_slug = base[len(common_prefix) + 1 :]
        product_slug = common_prefix
    else:
        parts = base.split("-")
        if len(parts) >= 2:
            city_slug = parts[-1]
            product_slug = "-".join(parts[:-1])
        else:
            city_slug = base
            product_slug = "Layanan"

    product_title = clean_slug_to_title(product_slug) or "Layanan"
    city_title = clean_slug_to_title(city_slug) or "Indonesia"
    return product_title, city_title


def process_html_file(
    file_path: Path,
    common_prefix: str,
    t1_pool: List[Tuple[str, str, str]],
    regional_pool: List[Tuple[str, str, str]],
    all_candidates: List[Tuple[str, str, str]],
) -> Tuple[bool, int, int]:
    html = file_path.read_text(encoding="utf-8", errors="ignore")
    current_name = file_path.name
    product_title, current_city_title = parse_page_context(current_name, common_prefix)

    # Filter out current page from candidate pools
    page_t1 = [c for c in t1_pool if c[0] != current_name]
    page_reg = [c for c in regional_pool if c[0] != current_name]
    page_all = [c for c in all_candidates if c[0] != current_name]

    # Target content section only
    content_match = re.search(
        r"(<div[^>]*class=[\"'][^\"']*entry-content[^\"']*[\"'][^>]*>|<article\b[^>]*>|<main\b[^>]*>)(.*?)(</article>|</main>|<footer|<!-- \.entry-content)",
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not content_match:
        return False, 0, 0

    content_start = content_match.start(2)
    content_end = content_match.end(2)
    content_body = content_match.group(2)

    img_matches = list(re.finditer(r"<img\b[^>]*>", content_body, re.IGNORECASE))
    if not img_matches:
        return False, 0, 0

    replacements: List[Tuple[int, int, str]] = []
    links_added = 0
    alts_enriched = 0

    for idx, m in enumerate(img_matches):
        img_tag = m.group(0)
        img_start, img_end = m.start(), m.end()

        # Check if img is already wrapped in an anchor
        pre = content_body[max(0, img_start - 300) : img_start]
        is_in_anchor = False
        a_open_idx = pre.lower().rfind("<a ")
        if a_open_idx != -1:
            a_close_idx = pre.lower().rfind("</a>")
            if a_close_idx < a_open_idx:
                is_in_anchor = True

        src_m = re.search(r'src=["\']([^"\']+)["\']', img_tag, re.IGNORECASE)
        alt_m = re.search(r'alt=["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
        src = src_m.group(1) if src_m else ""
        existing_alt = alt_m.group(1).strip() if alt_m else ""

        img_kw = extract_image_keywords(src)
        needs_alt = not existing_alt

        if is_in_anchor:
            # Preserve anchor, update alt if empty
            if needs_alt:
                desc_parts = [product_title]
                if img_kw and img_kw.lower() not in product_title.lower():
                    desc_parts.append(img_kw)
                desc_parts.append(current_city_title)
                new_alt = " ".join(desc_parts)

                if alt_m:
                    new_tag = img_tag[: alt_m.start(1)] + new_alt + img_tag[alt_m.end(1) :]
                else:
                    new_tag = img_tag[:-1] + f' alt="{new_alt}">'
                replacements.append((img_start, img_end, new_tag))
                alts_enriched += 1
        else:
            # Unlinked image: pick target city using 80/20 Pareto rule
            seed_str = f"{current_name}:{src}:{idx}"
            seed_int = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
            prob = seed_int % 100

            if prob < 80 and page_t1:
                target_file, target_prod, target_city = page_t1[seed_int % len(page_t1)]
            elif page_reg:
                target_file, target_prod, target_city = page_reg[seed_int % len(page_reg)]
            elif page_all:
                target_file, target_prod, target_city = page_all[seed_int % len(page_all)]
            else:
                continue

            # Alt phrasing variations
            var_idx = (seed_int >> 8) % 4
            if var_idx == 0:
                alt_base = f"{product_title} {target_city}"
            elif var_idx == 1:
                alt_base = f"Jual & Pasang {product_title} di {target_city}"
            elif var_idx == 2:
                alt_base = f"Spesialis {product_title} Berkualitas {target_city}"
            else:
                alt_base = f"Pemasangan {product_title} Proyek {target_city}"

            # Blend image keyword if distinct
            if img_kw and img_kw.lower() not in alt_base.lower():
                alt_base = f"{alt_base} - {img_kw}"

            if alt_m:
                new_img_tag = img_tag[: alt_m.start(1)] + alt_base + img_tag[alt_m.end(1) :]
            else:
                new_img_tag = img_tag[:-1] + f' alt="{alt_base}">'

            wrapped_tag = f'<a href="/{target_file}" title="{product_title} {target_city}">{new_img_tag}</a>'
            replacements.append((img_start, img_end, wrapped_tag))
            links_added += 1
            alts_enriched += 1

    if not replacements:
        return False, 0, 0

    # Apply replacements from back to front to maintain character offsets
    replacements.sort(key=lambda x: x[0], reverse=True)
    mod_body = content_body
    for s, e, new_str in replacements:
        mod_body = mod_body[:s] + new_str + mod_body[e:]

    new_html = html[:content_start] + mod_body + html[content_end:]
    file_path.write_text(new_html, encoding="utf-8")
    return True, links_added, alts_enriched


def run(root_dir: str, domain: Optional[str] = None, check_only: bool = False) -> Dict[str, object]:
    root = Path(root_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"Target directory does not exist: {root}")

    detected_dom = domain or detect_domain(root)

    # 1. Robots.txt
    robots_changed, robots_status = False, "unchanged"
    if not check_only:
        robots_changed, robots_status = ensure_robots_txt(root, detected_dom)

    # 2. HTML Files Scan
    html_files = [f for f in root.glob("*.html") if f.name not in UTILITY_PAGES]
    html_names = [f.name for f in html_files]

    common_prefix = detect_common_product_prefix(html_names)

    # Build candidate target pools
    all_candidates: List[Tuple[str, str, str]] = []
    t1_pool: List[Tuple[str, str, str]] = []
    regional_pool: List[Tuple[str, str, str]] = []

    for f_name in html_names:
        p_title, c_title = parse_page_context(f_name, common_prefix)
        entry = (f_name, p_title, c_title)
        all_candidates.append(entry)

        # Check if city matches Tier 1
        city_slug = f_name[:-5].replace(common_prefix + "-", "") if common_prefix else f_name[:-5].split("-")[-1]
        if city_slug.lower() in TIER1_CITIES:
            t1_pool.append(entry)
        else:
            regional_pool.append(entry)

    modified_files = 0
    total_links_added = 0
    total_alts_enriched = 0

    if not check_only:
        for file_path in html_files:
            changed, links, alts = process_html_file(file_path, common_prefix, t1_pool, regional_pool, all_candidates)
            if changed:
                modified_files += 1
                total_links_added += links
                total_alts_enriched += alts

    return {
        "status": "success",
        "domain": detected_dom,
        "is_tracker": is_tracker_domain(detected_dom),
        "robots_status": robots_status,
        "robots_changed": robots_changed,
        "total_html_files": len(html_files),
        "tier1_city_pages": len(t1_pool),
        "regional_city_pages": len(regional_pool),
        "modified_files": modified_files,
        "total_links_added": total_links_added,
        "total_alts_enriched": total_alts_enriched,
    }


def main():
    parser = argparse.ArgumentParser(description="Portfolio SEO Robots.txt & Image Linking Engine")
    parser.add_argument("--root", default=".", help="Root directory of repository")
    parser.add_argument("--domain", default=None, help="Explicit domain override")
    parser.add_argument("--check-only", action="store_true", help="Audit mode without file mutation")
    args = parser.parse_args()

    result = run(args.root, args.domain, args.check_only)
    print(
        f"Domain: {result['domain']} (Tracker: {result['is_tracker']}) | "
        f"Robots: {result['robots_status']} | "
        f"Files: {result['modified_files']}/{result['total_html_files']} modified | "
        f"Links: +{result['total_links_added']} | "
        f"Alts: +{result['total_alts_enriched']}"
    )


if __name__ == "__main__":
    main()
