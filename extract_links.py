#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "tqdm",
# ]
# ///
"""Extrai, limpa e valida links de conversas exportadas do WhatsApp."""

import argparse
import asyncio
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
from tqdm import tqdm

# Regex para extrair URLs
URL_PATTERN = re.compile(r'https?://[^\s<>"\')\]]+')

# Regex para extrair contexto da mensagem WhatsApp
# Formato: DD/MM/YYYY HH:MM da manhã/tarde/noite/madrugada - Nome: Mensagem
MESSAGE_PATTERN = re.compile(
    r'^(\d{2}/\d{2}/\d{4})\s+\d{1,2}:\d{2}\s+da\s+(?:manhã|tarde|noite|madrugada)\s+-\s+([^:]+):\s*(.+)$',
    re.MULTILINE
)

# Parâmetros de tracking a remover
TRACKING_PARAMS = {
    # UTM parameters
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
    # Facebook/Meta
    'fbclid', 'igsh', 'igshid',
    # Google
    'gclid', 'gclsrc',
    # Genéricos
    'ref', 'rcm', 'source', 'mc_cid', 'mc_eid',
    # LinkedIn
    'trk', 'lipi', 'licu',
    # Amazon
    'tag', 'linkCode', 'linkId',
    # Outros
    'share', 'si',  # Spotify
}

# Parâmetros essenciais a preservar (por domínio)
ESSENTIAL_PARAMS = {
    'youtube.com': {'v', 't', 'list', 'index'},
    'youtu.be': {'t'},
    'twitter.com': {'s'},
    'x.com': {'s'},
    'open.spotify.com': {},  # path contém ID
    'docs.google.com': {},  # path contém ID
    'linkedin.com': {},
}


def clean_url(url: str) -> str:
    """Remove parâmetros de tracking da URL, preservando parâmetros essenciais."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '').lower()

        # Obtém parâmetros essenciais para o domínio
        essential = ESSENTIAL_PARAMS.get(domain, set())

        # Filtra query params
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            filtered_params = {
                k: v for k, v in params.items()
                if k.lower() not in TRACKING_PARAMS or k.lower() in essential
            }
            new_query = urlencode(filtered_params, doseq=True) if filtered_params else ''
        else:
            new_query = ''

        # Remove fragmentos vazios e trailing slashes desnecessários
        fragment = parsed.fragment if parsed.fragment and not parsed.fragment.startswith('~') else ''

        # Reconstrói URL limpa
        clean = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/') if parsed.path != '/' else parsed.path,
            parsed.params,
            new_query,
            fragment
        ))

        return clean
    except Exception:
        return url


def extract_domain(url: str) -> str:
    """Extrai o domínio principal da URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '').lower()
        return domain
    except Exception:
        return 'unknown'


def generate_title(url: str, domain: str) -> str:
    """Gera um título legível a partir da URL."""
    try:
        parsed = urlparse(url)
        path = parsed.path.strip('/')

        # Casos especiais por domínio
        if 'linkedin.com' in domain:
            if '/in/' in path:
                # Perfil do LinkedIn
                name = path.split('/in/')[-1].split('/')[0]
                name = name.replace('-', ' ').title()
                return f"LinkedIn - {name}"
            elif '/posts/' in path or '/feed/' in path:
                return "LinkedIn - Post"
            elif '/company/' in path:
                company = path.split('/company/')[-1].split('/')[0]
                return f"LinkedIn - {company.replace('-', ' ').title()}"

        if 'youtube.com' in domain or 'youtu.be' in domain:
            return "YouTube - Vídeo"

        if 'instagram.com' in domain:
            if path:
                username = path.split('/')[0]
                return f"Instagram - @{username}"
            return "Instagram"

        if 'twitter.com' in domain or 'x.com' in domain:
            if path:
                username = path.split('/')[0]
                return f"X/Twitter - @{username}"
            return "X/Twitter"

        if 'docs.google.com' in domain:
            if '/document/' in path:
                return "Google Docs - Documento"
            elif '/spreadsheets/' in path:
                return "Google Sheets - Planilha"
            elif '/presentation/' in path:
                return "Google Slides - Apresentação"
            return "Google Docs"

        if 'open.spotify.com' in domain:
            if '/episode/' in path:
                return "Spotify - Podcast"
            elif '/track/' in path:
                return "Spotify - Música"
            elif '/playlist/' in path:
                return "Spotify - Playlist"
            return "Spotify"

        if 'github.com' in domain:
            parts = path.split('/')
            if len(parts) >= 2:
                return f"GitHub - {parts[0]}/{parts[1]}"
            return "GitHub"

        if 'medium.com' in domain:
            return "Medium - Artigo"

        if 'amazon.com' in domain or 'amazon.com.br' in domain:
            return "Amazon - Produto"

        # Genérico: usa o domínio e parte do path
        if path:
            slug = path.split('/')[-1]
            # Remove extensões
            slug = re.sub(r'\.[a-z]+$', '', slug)
            # Converte para título legível
            slug = re.sub(r'[-_]', ' ', slug)
            if len(slug) > 5 and len(slug) < 80:
                domain_name = domain.split('.')[0].title()
                return f"{domain_name} - {slug[:60]}"

        return domain.split('.')[0].title()
    except Exception:
        return domain


def parse_whatsapp_export(text: str) -> Iterator[dict]:
    """Extrai mensagens com URLs do texto exportado do WhatsApp."""
    current_date = None
    current_sender = None
    current_message = []

    for line in text.split('\n'):
        # Tenta extrair nova mensagem
        match = MESSAGE_PATTERN.match(line)
        if match:
            # Processa mensagem anterior se houver URLs
            if current_message:
                full_message = '\n'.join(current_message)
                for url in URL_PATTERN.findall(full_message):
                    yield {
                        'url_original': url,
                        'date': current_date,
                        'shared_by': current_sender,
                    }

            # Nova mensagem
            current_date = match.group(1)
            current_sender = match.group(2).strip()
            current_message = [match.group(3)]
        else:
            # Continuação da mensagem anterior
            if line.strip():
                current_message.append(line)

    # Processa última mensagem
    if current_message:
        full_message = '\n'.join(current_message)
        for url in URL_PATTERN.findall(full_message):
            yield {
                'url_original': url,
                'date': current_date,
                'shared_by': current_sender,
            }


async def validate_url(client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore) -> dict:
    """Valida uma URL via HEAD request."""
    async with semaphore:
        try:
            response = await client.head(url, follow_redirects=True, timeout=10.0)
            return {
                'status': 'valid' if response.status_code < 400 else 'invalid',
                'status_code': response.status_code,
                'final_url': str(response.url) if response.url != url else None,
            }
        except httpx.TimeoutException:
            return {'status': 'timeout', 'status_code': None, 'final_url': None}
        except httpx.RequestError:
            return {'status': 'error', 'status_code': None, 'final_url': None}
        except Exception:
            return {'status': 'error', 'status_code': None, 'final_url': None}


async def validate_urls(links: list[dict], concurrency: int = 10) -> list[dict]:
    """Valida múltiplas URLs em paralelo."""
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(
        headers={'User-Agent': 'Mozilla/5.0 (compatible; LinkValidator/1.0)'},
        follow_redirects=True,
    ) as client:
        tasks = []
        for link in links:
            task = validate_url(client, link['url'], semaphore)
            tasks.append(task)

        results = []
        with tqdm(total=len(tasks), desc="Validando URLs") as pbar:
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.append(result)
                pbar.update(1)

        # Mapeia resultados de volta (ordem pode ter mudado)
        # Refaz com gather para manter ordem
        results = await asyncio.gather(*[
            validate_url(client, link['url'], semaphore)
            for link in links
        ])

        for link, validation in zip(links, results):
            link.update(validation)

    return links


def extract_links(input_path: Path, limit: int | None = None) -> list[dict]:
    """Extrai e processa todos os links do arquivo."""
    text = input_path.read_text(encoding='utf-8')

    seen_urls: dict[str, dict] = {}

    for item in parse_whatsapp_export(text):
        url_original = item['url_original']
        url_clean = clean_url(url_original)

        # Ignora se já vimos essa URL limpa
        if url_clean in seen_urls:
            continue

        domain = extract_domain(url_clean)
        title = generate_title(url_clean, domain)

        seen_urls[url_clean] = {
            'url': url_clean,
            'url_original': url_original if url_original != url_clean else None,
            'domain': domain,
            'title': title,
            'shared_by': item['shared_by'],
            'date': item['date'],
            'status': 'pending',
        }

        if limit and len(seen_urls) >= limit:
            break

    return list(seen_urls.values())


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'input_file',
        type=Path,
        help='Arquivo de conversa exportada do WhatsApp (.txt)',
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Arquivo de saída JSON (default: stdout)',
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Valida URLs via HEAD request',
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        default=10,
        help='Número de requisições paralelas para validação (default: 10)',
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limita número de links a processar',
    )
    parser.add_argument(
        '--format',
        choices=['json', 'jsonl'],
        default='json',
        help='Formato de saída (default: json)',
    )
    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Erro: arquivo não encontrado: {args.input_file}", file=sys.stderr)
        return 2

    # Extrai links
    print(f"Extraindo links de {args.input_file}...", file=sys.stderr)
    links = extract_links(args.input_file, limit=args.limit)
    print(f"Encontrados {len(links)} links únicos", file=sys.stderr)

    # Valida se solicitado
    if args.validate:
        print(f"Validando URLs (concurrency={args.concurrency})...", file=sys.stderr)
        links = asyncio.run(validate_urls(links, args.concurrency))

        # Estatísticas
        valid = sum(1 for l in links if l.get('status') == 'valid')
        invalid = sum(1 for l in links if l.get('status') == 'invalid')
        timeout = sum(1 for l in links if l.get('status') == 'timeout')
        error = sum(1 for l in links if l.get('status') == 'error')
        print(f"Validação: {valid} válidos, {invalid} inválidos, {timeout} timeout, {error} erros", file=sys.stderr)

    # Remove campos None para saída mais limpa
    for link in links:
        link = {k: v for k, v in link.items() if v is not None}

    # Saída
    if args.format == 'jsonl':
        output_text = '\n'.join(
            json.dumps(link, ensure_ascii=False) for link in links
        )
    else:
        output_text = json.dumps(links, ensure_ascii=False, indent=2)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text, encoding='utf-8')
        print(f"Salvo em {args.output}", file=sys.stderr)
    else:
        print(output_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
