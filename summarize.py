#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "anthropic",
#     "openai",
#     "google-genai",
# ]
# ///
"""Gera resumos de conversas do WhatsApp usando LLMs.

Lê mensagens de stdin ou arquivo e gera um resumo estruturado.
Suporta múltiplos provedores: Anthropic, OpenAI, Ollama.

Exemplo:
    cat mensagens.txt | uv run summarize.py --provider anthropic
    uv run summarize.py --input semanas/semana_2025-08-05.txt --estimate

Flags úteis:
- ``--skip_validation``: ignora validação de formato (útil para conteúdos
  segmentados onde mensagens ocupam várias linhas)
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path


def load_dotenv():
    """Carrega variáveis do arquivo .env se existir."""
    env_file = Path(__file__).parent / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                if key and value and key not in os.environ:
                    os.environ[key] = value


load_dotenv()

# Preços por milhão de tokens (USD) - Janeiro 2026
# Qualidade para resumos em português: ★★★★★ = excelente, ★☆☆☆☆ = básico
PRICING = {
    'anthropic': {
        # ★★★★★ Melhor qualidade para português, nuances culturais
        'claude-sonnet-4-20250514': {'input': 3.0, 'output': 15.0, 'quality': 5},
        'claude-3-5-sonnet-20241022': {'input': 3.0, 'output': 15.0, 'quality': 5},
        # ★★★☆☆ Bom para tarefas simples, pode perder nuances
        'claude-3-haiku-20240307': {'input': 0.25, 'output': 1.25, 'quality': 3},
    },
    'openai': {
        # ★★★★☆ Muito bom, às vezes mais formal que o necessário
        'gpt-4o': {'input': 2.5, 'output': 10.0, 'quality': 4},
        # ★★★☆☆ Bom custo-benefício, pode simplificar demais
        'gpt-4o-mini': {'input': 0.15, 'output': 0.6, 'quality': 3},
    },
    'google': {
        # ★★★★★ Gemini 3 - última geração (preview)
        'gemini-3-pro-preview': {'input': 2.0, 'output': 12.0, 'quality': 5},
        'gemini-3-flash-preview': {'input': 0.50, 'output': 3.0, 'quality': 4},
        # ★★★★★ Gemini 2.5 - estável
        'gemini-2.5-pro': {'input': 1.25, 'output': 10.0, 'quality': 5},
        'gemini-2.5-flash': {'input': 0.30, 'output': 2.50, 'quality': 4},
        'gemini-2.5-flash-lite': {'input': 0.10, 'output': 0.40, 'quality': 4},
        # ★★★☆☆ Gemini 2.0 - legacy
        'gemini-2.0-flash': {'input': 0.10, 'output': 0.40, 'quality': 3},
    },
    'ollama': {
        'llama3': {'input': 0.0, 'output': 0.0, 'quality': 2},
        'mistral': {'input': 0.0, 'output': 0.0, 'quality': 2},
    }
}

DEFAULT_MODELS = {
    'anthropic': 'claude-sonnet-4-20250514',
    'openai': 'gpt-4o',
    'google': 'gemini-2.5-pro',
    'ollama': 'llama3',
}

SYSTEM_PROMPT = """Você é um assistente especializado em analisar conversas de grupos de WhatsApp sobre educação e inteligência artificial. Seu objetivo é gerar resumos estruturados, claros e úteis."""

def load_prompt_template() -> str:
    """Carrega o template do prompt do arquivo PROMPT.md."""
    prompt_file = Path(__file__).parent / 'PROMPT.md'
    if not prompt_file.exists():
        print(f"Erro: arquivo PROMPT.md não encontrado em {prompt_file}", file=sys.stderr)
        sys.exit(1)
    return prompt_file.read_text()


USER_PROMPT_TEMPLATE = load_prompt_template()


def estimate_tokens(text: str) -> int:
    """Estima número de tokens (aproximação: 4 chars = 1 token em português)."""
    return len(text) // 4


def estimate_cost(input_tokens: int, output_tokens: int, provider: str, model: str) -> float:
    """Calcula custo estimado em USD."""
    if provider not in PRICING or model not in PRICING[provider]:
        return 0.0

    prices = PRICING[provider][model]
    input_cost = (input_tokens / 1_000_000) * prices['input']
    output_cost = (output_tokens / 1_000_000) * prices['output']
    return input_cost + output_cost


def get_cache_path(content_hash: str, provider: str, model: str) -> Path:
    """Retorna caminho do arquivo de cache."""
    cache_dir = Path('.cache/summarize')
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{content_hash}_{provider}_{model.replace('/', '_')}.json"


def get_cached_result(content: str, provider: str, model: str) -> str | None:
    """Retorna resultado cacheado se existir."""
    content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
    cache_path = get_cache_path(content_hash, provider, model)

    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text())
            return data.get('summary')
        except (json.JSONDecodeError, KeyError):
            return None
    return None


def save_to_cache(content: str, summary: str, provider: str, model: str) -> None:
    """Salva resultado no cache."""
    content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
    cache_path = get_cache_path(content_hash, provider, model)

    data = {
        'content_hash': content_hash,
        'provider': provider,
        'model': model,
        'summary': summary,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def call_anthropic(messages: str, model: str, max_tokens: int) -> str:
    """Chama API da Anthropic."""
    import anthropic

    client = anthropic.Anthropic()
    prompt = USER_PROMPT_TEMPLATE.format(messages=messages)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def call_openai(messages: str, model: str, max_tokens: int) -> str:
    """Chama API da OpenAI."""
    import openai

    client = openai.OpenAI()
    prompt = USER_PROMPT_TEMPLATE.format(messages=messages)

    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content


def call_ollama(messages: str, model: str, max_tokens: int) -> str:
    """Chama Ollama local via API compatível com OpenAI."""
    import openai

    client = openai.OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama"
    )
    prompt = USER_PROMPT_TEMPLATE.format(messages=messages)

    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content


def call_google(messages: str, model: str, max_tokens: int) -> str:
    """Chama API do Google Gemini."""
    from google import genai
    from google.genai import types

    client = genai.Client()
    prompt = USER_PROMPT_TEMPLATE.format(messages=messages)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=max_tokens,
        )
    )

    # Verifica se a resposta foi truncada
    if response.candidates:
        candidate = response.candidates[0]
        finish_reason = candidate.finish_reason
        # Verifica se não terminou normalmente (STOP)
        if finish_reason and str(finish_reason) not in ('STOP', 'FinishReason.STOP', '1'):
            print(f"Aviso: resposta truncada (finish_reason={finish_reason})", file=sys.stderr)
            if 'MAX_TOKENS' in str(finish_reason):
                print(f"  -> Limite de tokens atingido. Aumente --max_tokens", file=sys.stderr)

    return response.text


def call_llm(messages: str, provider: str, model: str, max_tokens: int, retries: int = 5) -> str:
    """Chama LLM com retry e backoff exponencial.

    OBS: Esta assinatura é substituída abaixo por uma versão com
    parâmetros de backoff configuráveis via CLI. Mantida por retrocompat.
    """
    providers = {
        'anthropic': call_anthropic,
        'openai': call_openai,
        'google': call_google,
        'ollama': call_ollama,
    }

    if provider not in providers:
        raise ValueError(f"Provedor desconhecido: {provider}")

    call_fn = providers[provider]
    last_error = None

    for attempt in range(retries):
        try:
            return call_fn(messages, model, max_tokens)
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                # Extrai tempo de espera do erro 429 se disponível
                wait_time = 2 ** attempt
                error_str = str(e)
                if '429' in error_str and 'retry' in error_str.lower():
                    import re
                    match = re.search(r'retry.*?(\d+)', error_str.lower())
                    if match:
                        wait_time = int(match.group(1)) + 5  # adiciona margem
                print(f"Erro: Rate limit. Aguardando {wait_time}s...", file=sys.stderr)
                time.sleep(wait_time)

    raise last_error


def call_llm_with_backoff(
    messages: str,
    provider: str,
    model: str,
    max_tokens: int,
    *,
    retries: int = 5,
    retry_base: int = 2,
    retry_max: int = 120,
    retry_jitter: float = 0.0,
    pre_sleep: int = 0,
) -> str:
    """Chama LLM com parâmetros de backoff configuráveis.

    - retries: número de tentativas
    - retry_base: base para o backoff exponencial (segundos)
    - retry_max: limite superior do tempo de espera entre tentativas
    - retry_jitter: fração de jitter aleatório (0.2 → ±20%)
    - pre_sleep: aguarda N segundos antes da primeira chamada
    """
    import random

    providers = {
        'anthropic': call_anthropic,
        'openai': call_openai,
        'google': call_google,
        'ollama': call_ollama,
    }

    if provider not in providers:
        raise ValueError(f"Provedor desconhecido: {provider}")

    call_fn = providers[provider]

    if pre_sleep > 0:
        print(f"Aguardando {pre_sleep}s antes de iniciar (cooldown)...", file=sys.stderr)
        time.sleep(pre_sleep)

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            return call_fn(messages, model, max_tokens)
        except Exception as e:  # noqa: BLE001
            last_error = e
            if attempt >= retries - 1:
                break

            # Espera recomendada por erro (ex.: 'retry in N')
            wait_time = retry_base * (2 ** attempt)
            wait_time = min(wait_time, retry_max)

            msg = str(e)
            # Extrai segundos sugeridos (se houver) e aplica margem
            try:
                import re as _re
                m = _re.search(r"retry\D+(\d+)", msg.lower())
                if m:
                    wait_time = min(int(m.group(1)) + 5, retry_max)
            except Exception:
                pass

            # Aplica jitter
            if retry_jitter > 0:
                delta = wait_time * retry_jitter
                wait_time = max(1, int(random.uniform(wait_time - delta, wait_time + delta)))

            print(f"Rate limit/erro transitório: aguardando {wait_time}s (tentativa {attempt+2}/{retries})...", file=sys.stderr)
            # Mostra tipo de erro uma vez
            err_name = type(e).__name__
            print(f"  Detalhe: {err_name}: {msg}", file=sys.stderr)
            time.sleep(wait_time)

    assert last_error is not None
    raise last_error


def validate_input(content: str) -> tuple[bool, str]:
    """Valida se o conteúdo parece ser uma conversa de WhatsApp.

    Mais tolerante com mensagens multilinha: procura padrões de início de
    mensagem nas primeiras 500 linhas, mas aceita com apenas 1 ocorrência
    (conversas curtas/segmentadas).
    """
    if not content.strip():
        return False, "Conteúdo vazio"

    lines = content.splitlines()
    if len(lines) < 3:
        return False, f"Muito poucas linhas ({len(lines)})"

    import re
    # Padrão semelhante ao usado em stats.py
    msg_start = re.compile(
        r"^\d{2}/\d{2}/\d{4} \d{1,2}:\d{2}(?:\sda\s(?:madrugada|manhã|tarde|noite))? - [^:]+: .+"
    )
    matches = sum(1 for line in lines[:500] if msg_start.match(line))
    if matches >= 1:
        return True, "OK"

    # Fallback: qualquer data no início da linha
    date_bol = re.compile(r"(?m)^\d{2}/\d{2}/\d{4}")
    if len(date_bol.findall(content)) >= 1:
        return True, "OK"

    return False, "Não parece ser formato WhatsApp"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--input', '-i',
        help='Arquivo de entrada (default: stdin)'
    )
    parser.add_argument(
        '--output', '-o',
        help='Arquivo de saída (default: stdout)'
    )
    parser.add_argument(
        '--provider', '-p',
        choices=['anthropic', 'openai', 'google', 'ollama'],
        default='anthropic',
        help='Provedor de LLM (default: anthropic)'
    )
    parser.add_argument(
        '--model', '-m',
        help='Modelo específico (default: depende do provedor)'
    )
    parser.add_argument(
        '--max_tokens',
        type=int,
        default=4096,
        help='Máximo de tokens na resposta (default: 4096)'
    )
    parser.add_argument(
        '--retries',
        type=int,
        default=5,
        help='Número de tentativas em caso de rate limit (default: 5)'
    )
    parser.add_argument(
        '--retry_base',
        type=int,
        default=2,
        help='Base do backoff exponencial em segundos (default: 2)'
    )
    parser.add_argument(
        '--retry_max',
        type=int,
        default=120,
        help='Tempo máximo de espera entre tentativas (default: 120)'
    )
    parser.add_argument(
        '--retry_jitter',
        type=float,
        default=0.25,
        help='Jitter aleatório (fração, 0.25 = ±25%) (default: 0.25)'
    )
    parser.add_argument(
        '--pre_sleep',
        type=int,
        default=0,
        help='Espera inicial antes da primeira chamada, em segundos (default: 0)'
    )
    parser.add_argument(
        '--estimate',
        action='store_true',
        help='Apenas mostra estimativa de custo sem executar'
    )
    parser.add_argument(
        '--no_cache',
        action='store_true',
        help='Ignora cache e força nova geração'
    )
    parser.add_argument(
        '--skip_validation',
        action='store_true',
        help='Ignora validação de formato (aceita qualquer texto)'
    )
    parser.add_argument(
        '--fallback_model',
        help='Modelo alternativo se ocorrerem erros/rate limit (ex.: gemini-2.5-flash-lite)'
    )

    args = parser.parse_args()

    # Define modelo
    model = args.model or DEFAULT_MODELS[args.provider]

    # Lê entrada
    if args.input:
        try:
            content = Path(args.input).read_text()
        except FileNotFoundError:
            print(f"Erro: arquivo '{args.input}' não encontrado", file=sys.stderr)
            return 2
    else:
        if sys.stdin.isatty():
            print("Erro: nenhuma entrada. Use --input ou pipe", file=sys.stderr)
            return 1
        content = sys.stdin.read()

    # Valida entrada
    if not args.skip_validation:
        valid, msg = validate_input(content)
        if not valid:
            print(f"Erro: entrada inválida - {msg}", file=sys.stderr)
            return 1

    # Calcula estimativas
    prompt = USER_PROMPT_TEMPLATE.format(messages=content)
    input_tokens = estimate_tokens(SYSTEM_PROMPT + prompt)
    output_tokens = args.max_tokens  # estimativa pessimista
    cost = estimate_cost(input_tokens, output_tokens, args.provider, model)

    if args.estimate:
        print(f"Provedor: {args.provider}")
        print(f"Modelo: {model}")
        print(f"Tokens de entrada (estimado): {input_tokens:,}")
        print(f"Tokens de saída (máximo): {output_tokens:,}")
        print(f"Custo estimado: ${cost:.4f} USD")

        if model in PRICING.get(args.provider, {}):
            prices = PRICING[args.provider][model]
            print(f"  - Entrada: ${(input_tokens/1_000_000)*prices['input']:.4f}")
            print(f"  - Saída: ${(output_tokens/1_000_000)*prices['output']:.4f}")

        return 0

    # Verifica cache
    if not args.no_cache:
        cached = get_cached_result(content, args.provider, model)
        if cached:
            print("(usando cache)", file=sys.stderr)
            if args.output:
                Path(args.output).write_text(cached)
            else:
                print(cached)
            return 0

    # Verifica API key
    if args.provider == 'anthropic' and not os.environ.get('ANTHROPIC_API_KEY'):
        print("Erro: ANTHROPIC_API_KEY não definida", file=sys.stderr)
        return 1
    if args.provider == 'openai' and not os.environ.get('OPENAI_API_KEY'):
        print("Erro: OPENAI_API_KEY não definida", file=sys.stderr)
        return 1
    if args.provider == 'google' and not os.environ.get('GOOGLE_API_KEY'):
        print("Erro: GOOGLE_API_KEY não definida", file=sys.stderr)
        return 1

    # Chama LLM
    print(f"Gerando resumo com {args.provider}/{model}...", file=sys.stderr)
    print(f"Tokens de entrada: ~{input_tokens:,}", file=sys.stderr)

    try:
        summary = call_llm_with_backoff(
            content,
            args.provider,
            model,
            args.max_tokens,
            retries=args.retries,
            retry_base=args.retry_base,
            retry_max=args.retry_max,
            retry_jitter=args.retry_jitter,
            pre_sleep=args.pre_sleep,
        )
    except Exception as e:
        if args.fallback_model:
            print(f"Falha com {args.provider}/{model}. Usando fallback: {args.fallback_model}", file=sys.stderr)
            try:
                summary = call_llm_with_backoff(
                    content,
                    args.provider,
                    args.fallback_model,
                    args.max_tokens,
                    retries=max(3, args.retries),
                    retry_base=args.retry_base,
                    retry_max=args.retry_max,
                    retry_jitter=args.retry_jitter,
                    pre_sleep=max(10, args.pre_sleep),
                )
            except Exception as e2:
                print(f"Erro na API (fallback): {e2}", file=sys.stderr)
                return 3
        else:
            print(f"Erro na API: {e}", file=sys.stderr)
            return 3

    # Salva no cache
    if not args.no_cache:
        save_to_cache(content, summary, args.provider, model)

    # Output
    if args.output:
        Path(args.output).write_text(summary)
        print(f"Resumo salvo em: {args.output}", file=sys.stderr)
    else:
        print(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
