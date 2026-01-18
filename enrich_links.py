#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "playwright",
# ]
# ///
"""Enriquece links com títulos e descrições extraídos via browser headless."""

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


def extract_metadata(page) -> dict:
    """Extrai título e descrição da página carregada."""
    metadata = {}

    # Título: tenta várias fontes
    try:
        # 1. og:title (melhor para compartilhamento)
        og_title = page.locator('meta[property="og:title"]').get_attribute('content', timeout=1000)
        if og_title:
            metadata['title'] = og_title.strip()
    except Exception:
        pass

    if 'title' not in metadata:
        try:
            # 2. twitter:title
            tw_title = page.locator('meta[name="twitter:title"]').get_attribute('content', timeout=1000)
            if tw_title:
                metadata['title'] = tw_title.strip()
        except Exception:
            pass

    if 'title' not in metadata:
        try:
            # 3. <title> tag
            title = page.title()
            if title:
                metadata['title'] = title.strip()
        except Exception:
            pass

    # Descrição: tenta várias fontes
    try:
        # 1. og:description
        og_desc = page.locator('meta[property="og:description"]').get_attribute('content', timeout=1000)
        if og_desc:
            metadata['description'] = og_desc.strip()[:500]
    except Exception:
        pass

    if 'description' not in metadata:
        try:
            # 2. meta description
            meta_desc = page.locator('meta[name="description"]').get_attribute('content', timeout=1000)
            if meta_desc:
                metadata['description'] = meta_desc.strip()[:500]
        except Exception:
            pass

    if 'description' not in metadata:
        try:
            # 3. twitter:description
            tw_desc = page.locator('meta[name="twitter:description"]').get_attribute('content', timeout=1000)
            if tw_desc:
                metadata['description'] = tw_desc.strip()[:500]
        except Exception:
            pass

    return metadata


def enrich_link(browser, link: dict, timeout: int = 15000) -> dict:
    """Visita um link e extrai metadados."""
    url = link['url']
    result = link.copy()

    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1280, 'height': 720},
        locale='pt-BR',
    )

    try:
        page = context.new_page()

        # Bloqueia recursos pesados para acelerar
        page.route('**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,eot}', lambda route: route.abort())
        page.route('**/*analytics*', lambda route: route.abort())
        page.route('**/*tracking*', lambda route: route.abort())

        page.goto(url, wait_until='domcontentloaded', timeout=timeout)

        # Espera um pouco para JS carregar
        page.wait_for_timeout(2000)

        metadata = extract_metadata(page)

        if metadata.get('title'):
            result['title'] = metadata['title']
            result['title_source'] = 'extracted'

        if metadata.get('description'):
            result['description'] = metadata['description']

        result['enriched'] = True
        result['enrich_status'] = 'success'

    except PlaywrightTimeout:
        result['enriched'] = False
        result['enrich_status'] = 'timeout'
    except Exception as e:
        result['enriched'] = False
        result['enrich_status'] = f'error: {str(e)[:100]}'
    finally:
        context.close()

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'input_file',
        type=Path,
        help='Arquivo JSON de links (gerado por extract_links.py)',
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Arquivo de saída JSON (default: sobrescreve input)',
    )
    parser.add_argument(
        '--start',
        type=int,
        default=0,
        help='Índice inicial (para continuar de onde parou)',
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Número máximo de links a processar',
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=15000,
        help='Timeout por página em ms (default: 15000)',
    )
    parser.add_argument(
        '--skip-enriched',
        action='store_true',
        help='Pula links já enriquecidos',
    )
    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Erro: arquivo não encontrado: {args.input_file}", file=sys.stderr)
        return 2

    # Carrega links
    links = json.loads(args.input_file.read_text(encoding='utf-8'))
    total = len(links)
    output_path = args.output or args.input_file

    print(f"Total de links: {total}", file=sys.stderr)
    print(f"Iniciando do índice: {args.start}", file=sys.stderr)
    print(f"Salvando em: {output_path}", file=sys.stderr)
    print("-" * 50, file=sys.stderr)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        processed = 0
        end_idx = args.start + args.limit if args.limit else total

        for i in range(args.start, min(end_idx, total)):
            link = links[i]

            # Pula se já enriquecido
            if args.skip_enriched and link.get('enriched'):
                print(f"[{i+1}/{total}] SKIP (já enriquecido): {link['domain']}", file=sys.stderr)
                continue

            print(f"[{i+1}/{total}] Processando: {link['url'][:80]}...", file=sys.stderr)

            start_time = time.time()
            enriched = enrich_link(browser, link, timeout=args.timeout)
            elapsed = time.time() - start_time

            links[i] = enriched

            status = enriched.get('enrich_status', 'unknown')
            title_preview = enriched.get('title', 'N/A')[:50]
            print(f"         Status: {status} | Título: {title_preview}... ({elapsed:.1f}s)", file=sys.stderr)

            processed += 1

            # Salva progresso a cada 10 links
            if processed % 10 == 0:
                output_path.write_text(
                    json.dumps(links, ensure_ascii=False, indent=2),
                    encoding='utf-8'
                )
                print(f"         [Progresso salvo: {processed} links processados]", file=sys.stderr)

        browser.close()

    # Salva final
    output_path.write_text(
        json.dumps(links, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    # Estatísticas
    success = sum(1 for l in links if l.get('enrich_status') == 'success')
    timeout = sum(1 for l in links if l.get('enrich_status') == 'timeout')
    errors = sum(1 for l in links if l.get('enrich_status', '').startswith('error'))

    print("-" * 50, file=sys.stderr)
    print(f"Concluído! Processados: {processed}", file=sys.stderr)
    print(f"Sucesso: {success} | Timeout: {timeout} | Erros: {errors}", file=sys.stderr)
    print(f"Salvo em: {output_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
