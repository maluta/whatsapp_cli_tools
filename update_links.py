#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "playwright",
# ]
# ///
"""Atualiza links.json com novos links extraídos de arquivos de semana.

Uso:
    uv run update_links.py semanas/semana_2026-01-06_2026-01-12.txt
    uv run update_links.py semanas/semana_*.txt --enrich
    uv run update_links.py semanas/semana_2026-01-06_2026-01-12.txt --dry-run

Fluxo:
1. Carrega links existentes do JSON
2. Extrai links dos arquivos de semana
3. Identifica links novos (não presentes no JSON)
4. Opcionalmente enriquece os novos links via browser
5. Merge e salva o JSON atualizado
"""

import argparse
import json
import re
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Regex para extrair URLs
URL_PATTERN = re.compile(r'https?://[^\s<>"\')\]]+')

# Regex para extrair contexto da mensagem WhatsApp
MESSAGE_PATTERN = re.compile(
    r'^(\d{2}/\d{2}/\d{4})\s+\d{1,2}:\d{2}\s+da\s+(?:manhã|tarde|noite|madrugada)\s+-\s+([^:]+):\s*(.+)$',
    re.MULTILINE
)

# Parâmetros de tracking a remover
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
    'fbclid', 'igsh', 'igshid', 'gclid', 'gclsrc',
    'ref', 'rcm', 'source', 'mc_cid', 'mc_eid',
    'trk', 'lipi', 'licu', 'tag', 'linkCode', 'linkId',
    'share', 'si',
}

ESSENTIAL_PARAMS = {
    'youtube.com': {'v', 't', 'list', 'index'},
    'youtu.be': {'t'},
    'docs.google.com': {},
}


def clean_url(url: str) -> str:
    """Remove parâmetros de tracking da URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '').lower()
        essential = ESSENTIAL_PARAMS.get(domain, set())

        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            filtered = {k: v for k, v in params.items()
                       if k.lower() not in TRACKING_PARAMS or k.lower() in essential}
            new_query = urlencode(filtered, doseq=True) if filtered else ''
        else:
            new_query = ''

        fragment = parsed.fragment if parsed.fragment and not parsed.fragment.startswith('~') else ''

        return urlunparse((
            parsed.scheme, parsed.netloc,
            parsed.path.rstrip('/') if parsed.path != '/' else parsed.path,
            parsed.params, new_query, fragment
        ))
    except Exception:
        return url


def extract_domain(url: str) -> str:
    """Extrai o domínio principal da URL."""
    try:
        return urlparse(url).netloc.replace('www.', '').lower()
    except Exception:
        return 'unknown'


def generate_title(url: str, domain: str) -> str:
    """Gera um título legível a partir da URL."""
    try:
        parsed = urlparse(url)
        path = parsed.path.strip('/')

        if 'linkedin.com' in domain:
            if '/in/' in path:
                name = path.split('/in/')[-1].split('/')[0].replace('-', ' ').title()
                return f"LinkedIn - {name}"
            elif '/posts/' in path or '/feed/' in path:
                return "LinkedIn - Post"
        if 'youtube.com' in domain or 'youtu.be' in domain:
            return "YouTube - Vídeo"
        if 'instagram.com' in domain:
            if path:
                return f"Instagram - @{path.split('/')[0]}"
            return "Instagram"
        if 'docs.google.com' in domain:
            if '/document/' in path:
                return "Google Docs - Documento"
            elif '/spreadsheets/' in path:
                return "Google Sheets - Planilha"
            return "Google Docs"
        if 'open.spotify.com' in domain:
            if '/episode/' in path:
                return "Spotify - Podcast"
            return "Spotify"

        if path:
            slug = re.sub(r'\.[a-z]+$', '', path.split('/')[-1])
            slug = re.sub(r'[-_]', ' ', slug)
            if 5 < len(slug) < 80:
                return f"{domain.split('.')[0].title()} - {slug[:60]}"

        return domain.split('.')[0].title()
    except Exception:
        return domain


def parse_whatsapp_export(text: str) -> Iterator[dict]:
    """Extrai mensagens com URLs do texto exportado do WhatsApp."""
    current_date = None
    current_sender = None
    current_message = []

    for line in text.split('\n'):
        match = MESSAGE_PATTERN.match(line)
        if match:
            if current_message:
                full_message = '\n'.join(current_message)
                for url in URL_PATTERN.findall(full_message):
                    yield {
                        'url_original': url,
                        'date': current_date,
                        'shared_by': current_sender,
                    }
            current_date = match.group(1)
            current_sender = match.group(2).strip()
            current_message = [match.group(3)]
        elif line.strip():
            current_message.append(line)

    if current_message:
        full_message = '\n'.join(current_message)
        for url in URL_PATTERN.findall(full_message):
            yield {
                'url_original': url,
                'date': current_date,
                'shared_by': current_sender,
            }


def extract_metadata(page) -> dict:
    """Extrai título e descrição da página carregada."""
    metadata = {}

    for selector, key in [
        ('meta[property="og:title"]', 'title'),
        ('meta[name="twitter:title"]', 'title'),
    ]:
        if key not in metadata:
            try:
                val = page.locator(selector).get_attribute('content', timeout=1000)
                if val:
                    metadata[key] = val.strip()
            except Exception:
                pass

    if 'title' not in metadata:
        try:
            title = page.title()
            if title:
                metadata['title'] = title.strip()
        except Exception:
            pass

    for selector, key in [
        ('meta[property="og:description"]', 'description'),
        ('meta[name="description"]', 'description'),
    ]:
        if key not in metadata:
            try:
                val = page.locator(selector).get_attribute('content', timeout=1000)
                if val:
                    metadata[key] = val.strip()[:500]
            except Exception:
                pass

    return metadata


def enrich_link(browser, link: dict, timeout: int = 15000) -> dict:
    """Visita um link e extrai metadados."""
    result = link.copy()
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        viewport={'width': 1280, 'height': 720},
        locale='pt-BR',
    )

    try:
        page = context.new_page()
        page.route('**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2}', lambda r: r.abort())
        page.goto(link['url'], wait_until='domcontentloaded', timeout=timeout)
        page.wait_for_timeout(2000)

        metadata = extract_metadata(page)
        if metadata.get('title'):
            result['title'] = metadata['title']
        if metadata.get('description'):
            result['description'] = metadata['description']

        result['enriched'] = True
        result['enrich_status'] = 'success'
    except PlaywrightTimeout:
        result['enriched'] = False
        result['enrich_status'] = 'timeout'
    except Exception as e:
        result['enriched'] = False
        result['enrich_status'] = f'error: {str(e)[:50]}'
    finally:
        context.close()

    return result


def load_existing_links(path: Path) -> tuple[list[dict], set[str]]:
    """Carrega links existentes e retorna lista + set de URLs."""
    if not path.exists():
        return [], set()

    links = json.loads(path.read_text(encoding='utf-8'))
    urls = {link['url'] for link in links}
    return links, urls


def extract_new_links(conversation_path: Path, existing_urls: set[str]) -> list[dict]:
    """Extrai links novos (não presentes em existing_urls)."""
    text = conversation_path.read_text(encoding='utf-8')
    new_links = []
    seen = set()

    for item in parse_whatsapp_export(text):
        url_clean = clean_url(item['url_original'])

        if url_clean in existing_urls or url_clean in seen:
            continue

        seen.add(url_clean)
        domain = extract_domain(url_clean)

        new_links.append({
            'url': url_clean,
            'url_original': item['url_original'] if item['url_original'] != url_clean else None,
            'domain': domain,
            'title': generate_title(url_clean, domain),
            'shared_by': item['shared_by'],
            'date': item['date'],
            'enriched': False,
        })

    return new_links


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'input_files',
        type=Path,
        nargs='+',
        help='Arquivo(s) de semana segmentados (.txt). Aceita glob: semanas/semana_*.txt',
    )
    parser.add_argument(
        '--links-json',
        type=Path,
        default=Path('links/links.json'),
        help='Arquivo JSON de links (default: links/links.json)',
    )
    parser.add_argument(
        '--enrich',
        action='store_true',
        help='Enriquece novos links via browser headless',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mostra novos links sem salvar',
    )
    args = parser.parse_args()

    # Verifica arquivos
    for f in args.input_files:
        if not f.exists():
            print(f"Erro: arquivo não encontrado: {f}", file=sys.stderr)
            return 2

    # Carrega links existentes
    existing_links, existing_urls = load_existing_links(args.links_json)
    print(f"Links existentes: {len(existing_links)}", file=sys.stderr)
    print(f"Processando {len(args.input_files)} arquivo(s)...", file=sys.stderr)

    # Extrai novos links de todos os arquivos
    all_new_links = []
    seen_in_batch = set()

    for input_file in args.input_files:
        file_links = extract_new_links(input_file, existing_urls | seen_in_batch)
        for link in file_links:
            seen_in_batch.add(link['url'])
        all_new_links.extend(file_links)
        if file_links:
            print(f"  {input_file.name}: {len(file_links)} novos links", file=sys.stderr)

    new_links = all_new_links
    print(f"Total de novos links: {len(new_links)}", file=sys.stderr)

    if not new_links:
        print("Nenhum link novo para adicionar.", file=sys.stderr)
        return 0

    if args.dry_run:
        print("\n[DRY RUN] Novos links:", file=sys.stderr)
        for link in new_links[:20]:
            print(f"  - {link['date']} | {link['domain']} | {link['url'][:60]}", file=sys.stderr)
        if len(new_links) > 20:
            print(f"  ... e mais {len(new_links) - 20} links", file=sys.stderr)
        return 0

    # Enriquece novos links se solicitado
    if args.enrich:
        print(f"\nEnriquecendo {len(new_links)} novos links...", file=sys.stderr)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for i, link in enumerate(new_links):
                print(f"[{i+1}/{len(new_links)}] {link['url'][:60]}...", file=sys.stderr)
                start = time.time()
                new_links[i] = enrich_link(browser, link)
                status = new_links[i].get('enrich_status', '?')
                print(f"         {status} ({time.time()-start:.1f}s)", file=sys.stderr)
            browser.close()

    # Merge: novos links no início (mais recentes primeiro)
    merged = new_links + existing_links

    # Salva
    args.links_json.parent.mkdir(parents=True, exist_ok=True)
    args.links_json.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    print(f"\nAtualizado: {args.links_json}", file=sys.stderr)
    print(f"Total de links: {len(merged)} (+{len(new_links)} novos)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
