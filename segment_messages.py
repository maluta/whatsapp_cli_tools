#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Extrai mensagens de um arquivo ZIP do WhatsApp filtrando por período.

Lê um arquivo ZIP exportado do WhatsApp e filtra as mensagens
entre as datas especificadas, enviando o resultado para stdout.

Exemplo:
    uv run segment_messages.py --zip_path chat.zip --start_date 01/01/2026 --end_date 07/01/2026
"""

import argparse
import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime

# Encodings comuns em exports do WhatsApp
ENCODINGS = ['utf-8', 'utf-8-sig', 'utf-16', 'latin-1']

# Padrão para detectar início de mensagem (DD/MM/YYYY)
DATE_PATTERN = re.compile(r"(\d{2}/\d{2}/\d{4})")


def find_txt_in_zip(zip_path: str, extract_dir: str) -> str | None:
    """Extrai conteúdo do ZIP e retorna caminho do primeiro .txt encontrado."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
    except zipfile.BadZipFile:
        print(f"Erro: '{zip_path}' não é um arquivo ZIP válido", file=sys.stderr)
        return None
    except FileNotFoundError:
        print(f"Erro: arquivo '{zip_path}' não encontrado", file=sys.stderr)
        return None

    for root, _, files in os.walk(extract_dir):
        for file in files:
            if file.endswith('.txt'):
                return os.path.join(root, file)

    print("Erro: nenhum arquivo .txt encontrado no ZIP", file=sys.stderr)
    return None


def filter_by_date(txt_path: str, start: datetime, end: datetime) -> str | None:
    """Filtra mensagens entre as datas especificadas.

    Tenta múltiplos encodings para compatibilidade com diferentes
    versões do export do WhatsApp.
    """
    for encoding in ENCODINGS:
        try:
            lines: list[str] = []
            include = False

            with open(txt_path, 'r', encoding=encoding) as f:
                for line in f:
                    match = DATE_PATTERN.match(line)
                    if match:
                        msg_date = datetime.strptime(match.group(1), "%d/%m/%Y")
                        include = start <= msg_date <= end

                    if include:
                        lines.append(line)

            return ''.join(lines)

        except UnicodeDecodeError:
            continue

    print(f"Erro: não foi possível decodificar '{txt_path}'", file=sys.stderr)
    return None


def parse_date(date_str: str) -> datetime | None:
    """Converte string DD/MM/YYYY para datetime."""
    try:
        return datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--zip_path',
        required=True,
        help='Caminho para o arquivo ZIP exportado do WhatsApp'
    )
    parser.add_argument(
        '--start_date',
        required=True,
        help='Data inicial no formato DD/MM/YYYY'
    )
    parser.add_argument(
        '--end_date',
        required=True,
        help='Data final no formato DD/MM/YYYY'
    )

    args = parser.parse_args()

    # Valida datas
    start = parse_date(args.start_date)
    if not start:
        print(f"Erro: data inicial inválida '{args.start_date}'", file=sys.stderr)
        return 1

    end = parse_date(args.end_date)
    if not end:
        print(f"Erro: data final inválida '{args.end_date}'", file=sys.stderr)
        return 1

    if start > end:
        print("Erro: data inicial maior que data final", file=sys.stderr)
        return 1

    # Processa ZIP
    with tempfile.TemporaryDirectory() as tmpdir:
        txt_path = find_txt_in_zip(args.zip_path, tmpdir)
        if not txt_path:
            return 2

        result = filter_by_date(txt_path, start, end)
        if result is None:
            return 1

        if not result.strip():
            print("Aviso: nenhuma mensagem encontrada no período", file=sys.stderr)
            return 0

        print(result, end='')

    return 0


if __name__ == "__main__":
    sys.exit(main())
