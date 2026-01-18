#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Adiciona uma introdução no início de arquivos de resumo.

Insere as linhas:
  Resumos do grupo "Aprendizados IA + Educação"
  Semana: DD/MM/AAAA - DD/MM/AAAA

As datas são extraídas do nome do arquivo, que deve conter dois
valores no formato ISO (YYYY-MM-DD), por exemplo:
  resumo_2025-08-05_2025-08-11.md
  resumo_semana_2025-08-12_2025-08-18.md

Filosofia UNIX:
- Aceita arquivo único, diretório (recursivo, exige --in_place) ou stdin ('-')
- Saída em stdout quando não usar --in_place
- Idempotente: não duplica cabeçalho se já existir (use --force para substituir)
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path


INTRO_TEXT = 'Resumos do grupo "Aprendizados IA + Educação"'

# Captura duas datas ISO (YYYY-MM-DD) em qualquer posição do nome
FILENAME_DATES = re.compile(r"(\d{4}-\d{2}-\d{2}).*?(\d{4}-\d{2}-\d{2})")


def iso_to_br(iso_date: str) -> str:
    """Converte 'YYYY-MM-DD' → 'DD/MM/YYYY'."""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def build_intro(start_iso: str, end_iso: str, style: str) -> str:
    """Monta o texto de introdução conforme estilo.

    Estilos:
    - 'plain': linhas simples
    - 'blockquote': prefixadas com '>'
    - 'heading': primeira linha como '##', segunda simples
    """
    start_br = iso_to_br(start_iso)
    end_br = iso_to_br(end_iso)

    if style == 'blockquote':
        return f"> {INTRO_TEXT}\n> Semana: {start_br} - {end_br}\n\n"
    if style == 'heading':
        return f"## {INTRO_TEXT}\nSemana: {start_br} - {end_br}\n\n"
    # plain
    return f"{INTRO_TEXT}\nSemana: {start_br} - {end_br}\n\n"


def detect_intro(text: str) -> bool:
    """Retorna True se o texto já possui a introdução nas primeiras linhas."""
    head = "\n".join(text.splitlines()[:5])
    return INTRO_TEXT in head


def extract_dates_from_name(path: Path) -> tuple[str, str] | None:
    """Extrai duas datas ISO do nome do arquivo.

    Retorna (start_iso, end_iso) ou None se não encontrado.
    """
    m = FILENAME_DATES.search(path.name)
    if not m:
        return None
    return m.group(1), m.group(2)


def process_text_for_file(text: str, path: Path, *, style: str, force: bool) -> str:
    """Gera conteúdo com a introdução para um arquivo específico."""
    dates = extract_dates_from_name(path)
    if not dates:
        raise ValueError(f"não foi possível extrair datas do nome: {path.name}")

    if detect_intro(text) and not force:
        return text  # idempotente

    intro = build_intro(dates[0], dates[1], style)

    # Se já houver intro e --force, remove bloco existente antes de inserir
    if detect_intro(text) and force:
        lines = text.splitlines()
        # Remove até a primeira linha em branco após a intro detectada
        i = 0
        while i < len(lines) and INTRO_TEXT not in lines[i]:
            i += 1
        if i < len(lines):
            i += 1
            while i < len(lines) and lines[i].strip() != "":
                i += 1
            if i < len(lines) and lines[i].strip() == "":
                i += 1
            text = "\n".join(lines[i:])

    return intro + text.lstrip("\ufeff")  # remove BOM no início, se houver


def process_file(path: Path, *, in_place: bool, style: str, force: bool) -> int:
    """Processa arquivo único, escrevendo in-place ou stdout."""
    if not path.exists():
        print(f"Erro: arquivo não encontrado: {path}", file=sys.stderr)
        return 2

    content = path.read_text(encoding="utf-8")
    try:
        new_content = process_text_for_file(content, path, style=style, force=force)
    except ValueError as e:
        print(f"Aviso: {e}", file=sys.stderr)
        return 1

    if in_place:
        if new_content != content:
            path.write_text(new_content, encoding="utf-8")
        return 0

    sys.stdout.write(new_content)
    return 0


def process_dir(root: Path, *, style: str, force: bool) -> int:
    """Processa todos os .md do diretório recursivamente (in-place)."""
    if not root.exists():
        print(f"Erro: diretório não encontrado: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print("Erro: caminho não é diretório", file=sys.stderr)
        return 1

    rc = 0
    for path in sorted(root.rglob("*.md")):
        try:
            content = path.read_text(encoding="utf-8")
            new_content = process_text_for_file(content, path, style=style, force=force)
            if new_content != content:
                path.write_text(new_content, encoding="utf-8")
        except ValueError as e:
            print(f"Aviso: {path.name}: {e}", file=sys.stderr)
            rc = 1
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--path",
        "-p",
        default="resumos",
        help="Arquivo, diretório ou '-' para stdin (default: resumos)",
    )
    parser.add_argument(
        "--in_place",
        action="store_true",
        help="Edita arquivos no local (obrigatório para diretórios)",
    )
    parser.add_argument(
        "--style",
        choices=["plain", "blockquote", "heading"],
        default="blockquote",
        help="Estilo da introdução (default: blockquote)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Substitui introdução existente, se houver",
    )
    # Suporte básico a stdin (exige datas explícitas)
    parser.add_argument("--start_date", help="Data inicial (DD/MM/AAAA ou YYYY-MM-DD) para stdin")
    parser.add_argument("--end_date", help="Data final (DD/MM/AAAA ou YYYY-MM-DD) para stdin")

    args = parser.parse_args()

    if args.path == "-":
        if sys.stdin.isatty():
            print("Erro: nenhuma entrada via stdin", file=sys.stderr)
            return 1
        text = sys.stdin.read()
        if not args.start_date or not args.end_date:
            print("Erro: use --start_date e --end_date com stdin", file=sys.stderr)
            return 1

        def to_iso(d: str) -> str:
            d = d.strip()
            if re.match(r"\d{4}-\d{2}-\d{2}$", d):
                return d
            if re.match(r"\d{2}/\d{2}/\d{4}$", d):
                return datetime.strptime(d, "%d/%m/%Y").strftime("%Y-%m-%d")
            raise ValueError(f"data inválida: {d}")

        try:
            start_iso = to_iso(args.start_date)
            end_iso = to_iso(args.end_date)
        except ValueError as e:
            print(f"Erro: {e}", file=sys.stderr)
            return 1

        intro = build_intro(start_iso, end_iso, args.style)
        sys.stdout.write(intro + text.lstrip("\ufeff"))
        return 0

    path = Path(args.path)
    if path.is_dir():
        if not args.in_place:
            print("Erro: para diretórios, use --in_place", file=sys.stderr)
            return 1
        return process_dir(path, style=args.style, force=args.force)
    elif path.is_file():
        return process_file(path, in_place=args.in_place, style=args.style, force=args.force)

    print(f"Erro: caminho não encontrado: {path}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

