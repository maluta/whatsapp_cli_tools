#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "markdown",
# ]
# ///
"""Gera site HTML estático a partir dos resumos markdown."""

import argparse
import html
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import markdown


# Template HTML base (estilo brutalist inspirado no core-mba.pro)
BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | IA+Educação</title>
  <meta name="description" content="{description}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
  <style>
:root {{
  --bg-primary: #f3f4f6;
  --bg-secondary: #ffffff;
  --text-primary: #000000;
  --text-secondary: #4b5563;
  --accent-blue: #2563eb;
  --accent-yellow: #fbbf24;
  --border-color: #000000;
  --border-light: #d1d5db;
  --font-main: 'Space Grotesk', -apple-system, sans-serif;
  --font-mono: 'Space Mono', monospace;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: var(--font-main);
  color: var(--text-primary);
  line-height: 1.6;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-primary);
  background-image: radial-gradient(circle, #00000015 1px, transparent 1px);
  background-size: 20px 20px;
}}
.migration-banner {{
  background: var(--text-primary);
  color: var(--bg-secondary);
  padding: 0.75rem 1.5rem;
  text-align: center;
  font-family: var(--font-mono);
  font-size: 0.875rem;
}}
.migration-banner a {{ color: var(--accent-yellow); text-decoration: underline; }}
.migration-banner .close-banner {{
  background: none;
  border: none;
  color: var(--bg-secondary);
  cursor: pointer;
  margin-left: 1rem;
  font-size: 1.25rem;
  vertical-align: middle;
}}
.header {{
  position: sticky;
  top: 0;
  background: var(--bg-secondary);
  border-bottom: 2px solid var(--border-color);
  z-index: 100;
  padding: 1rem 1.5rem;
}}
.header-content {{
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}}
.logo {{
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}}
.logo-bracket {{ color: var(--accent-blue); }}
.nav {{
  display: flex;
  align-items: center;
  gap: 1.5rem;
  font-family: var(--font-mono);
  font-size: 0.875rem;
}}
.nav a {{ color: var(--text-secondary); text-decoration: none; transition: color 0.15s; }}
.nav a:hover {{ color: var(--text-primary); }}
.nav-separator {{ color: var(--border-light); }}
.main {{
  flex: 1;
  max-width: 1200px;
  margin: 0 auto;
  padding: 3rem 1.5rem;
  width: 100%;
}}
/* Search */
.search-container {{ margin-bottom: 2rem; }}
.search-input {{
  width: 100%;
  padding: 1rem;
  font-family: var(--font-mono);
  font-size: 1rem;
  border: 2px solid var(--border-color);
  background: var(--bg-secondary);
  outline: none;
}}
.search-input:focus {{ box-shadow: 4px 4px 0 var(--border-color); }}
.search-input::placeholder {{ color: var(--text-secondary); }}
.search-stats {{
  margin-top: 0.5rem;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
}}
.search-results {{
  margin-top: 1.5rem;
  display: none;
}}
.search-results.active {{ display: block; }}
.search-result-item {{
  background: var(--bg-secondary);
  border: 2px solid var(--border-color);
  padding: 1.25rem;
  margin-bottom: 1rem;
  text-decoration: none;
  color: var(--text-primary);
  display: block;
  transition: all 0.15s;
}}
.search-result-item:hover {{
  transform: translateY(-2px);
  box-shadow: 4px 4px 0 var(--border-color);
}}
.search-result-title {{
  font-weight: 700;
  font-size: 1.125rem;
  margin-bottom: 0.5rem;
  color: var(--accent-blue);
}}
.search-result-meta {{
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}}
.search-result-snippet {{
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.6;
}}
.search-result-snippet mark {{
  background: var(--accent-yellow);
  color: var(--text-primary);
  padding: 0.1em 0.2em;
}}
.no-results {{
  text-align: center;
  padding: 3rem;
  color: var(--text-secondary);
  display: none;
}}
.no-results.active {{ display: block; }}
.page-header {{
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 2px solid var(--border-color);
}}
.page-title {{
  font-family: var(--font-mono);
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
}}
.page-subtitle {{ font-size: 1rem; color: var(--text-secondary); }}
.posts-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.5rem;
}}
.posts-grid.hidden {{ display: none; }}
.post-card {{
  background: var(--bg-secondary);
  border: 2px solid var(--border-color);
  padding: 1.5rem;
  text-decoration: none;
  color: var(--text-primary);
  transition: all 0.15s ease;
  display: flex;
  flex-direction: column;
}}
.post-card:hover {{
  transform: translateY(-2px);
  box-shadow: 4px 4px 0 var(--border-color);
}}
.post-card-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}}
.post-card-action {{
  font-family: var(--font-mono);
  font-size: 0.625rem;
  padding: 0.25rem 0.5rem;
  background: transparent;
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
  text-decoration: none;
  transition: all 0.15s;
}}
.post-card-action:hover {{
  border-color: #25D366;
  color: #25D366;
}}
.post-card-image {{
  width: 100%;
  height: 120px;
  background: var(--bg-primary);
  border: 1px dashed var(--border-light);
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 0.625rem;
  color: var(--text-secondary);
}}
.post-card-category {{
  font-family: var(--font-mono);
  font-size: 0.625rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--accent-blue);
  background: rgba(37, 99, 235, 0.1);
  padding: 0.25rem 0.5rem;
}}
.post-card-date {{
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
}}
.post-card-title {{
  font-size: 1.125rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  line-height: 1.3;
}}
.post-card-excerpt {{
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.5;
  flex: 1;
}}
.post-card-footer {{
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-light);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--accent-blue);
}}
.back-link {{
  display: inline-block;
  margin-bottom: 1.5rem;
  font-family: var(--font-mono);
  font-size: 0.875rem;
  color: var(--text-secondary);
  text-decoration: none;
}}
.back-link:hover {{ color: var(--text-primary); }}
.back-link::before {{ content: "< "; }}
.post-header {{
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 2px solid var(--border-color);
}}
.post-meta {{
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  font-family: var(--font-mono);
  font-size: 0.75rem;
}}
.post-category {{
  color: var(--accent-blue);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-weight: 700;
}}
.post-date {{ color: var(--text-secondary); }}
.post-title {{ font-size: 2rem; font-weight: 700; line-height: 1.2; }}
.post-week {{
  font-family: var(--font-mono);
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-top: 0.5rem;
}}
.content {{
  background: var(--bg-secondary);
  border: 2px solid var(--border-color);
  padding: 2rem;
}}
.content h2 {{
  font-size: 1.5rem;
  font-weight: 700;
  margin-top: 3rem;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-light);
}}
.content h2:first-child {{ margin-top: 0; }}
.content h3 {{ font-size: 1.125rem; font-weight: 700; margin-top: 2rem; margin-bottom: 0.5rem; }}
.content p {{ margin-bottom: 1rem; }}
.content ul, .content ol {{ margin-bottom: 1rem; padding-left: 1.5rem; }}
.content li {{ margin-bottom: 0.5rem; }}
.content li ul {{ margin-top: 0.5rem; margin-bottom: 0.5rem; }}
.content a {{ color: var(--accent-blue); text-decoration: none; border-bottom: 1px solid transparent; }}
.content a:hover {{ border-bottom-color: var(--accent-blue); }}
.content strong {{ font-weight: 700; }}
/* Links page */
.links-section {{ margin-bottom: 3rem; }}
.links-section-title {{
  font-family: var(--font-mono);
  font-size: 1.25rem;
  font-weight: 700;
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid var(--border-color);
}}
.links-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}}
.links-grid.hidden {{ display: none; }}
.link-item {{
  background: var(--bg-secondary);
  border: 2px solid var(--border-color);
  padding: 1rem;
  display: flex;
  flex-direction: column;
  text-decoration: none;
  color: var(--text-primary);
  transition: all 0.15s;
}}
.link-item:hover {{
  transform: translateY(-2px);
  box-shadow: 4px 4px 0 var(--border-color);
}}
.link-item.hidden {{ display: none; }}
.link-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}}
.link-domain {{
  font-family: var(--font-mono);
  font-size: 0.625rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--accent-blue);
  background: rgba(37, 99, 235, 0.1);
  padding: 0.25rem 0.5rem;
}}
.link-action {{
  font-family: var(--font-mono);
  font-size: 0.625rem;
  padding: 0.25rem 0.5rem;
  background: transparent;
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}}
.link-action:hover {{
  border-color: #25D366;
  color: #25D366;
}}
.link-title {{
  font-weight: 700;
  font-size: 0.95rem;
  margin-bottom: 0.75rem;
  color: var(--text-primary);
  line-height: 1.3;
  flex: 1;
  text-decoration: none;
  word-break: break-word;
  overflow-wrap: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}}
.link-title:hover {{
  color: var(--accent-blue);
}}
.link-qr {{
  width: 80px;
  height: 80px;
  background: var(--bg-primary);
  border: 1px dashed var(--border-light);
  margin: 0 auto 0.75rem auto;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-size: 0.625rem;
  color: var(--text-secondary);
}}
.link-footer {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-light);
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-secondary);
}}
.links-count {{
  font-family: var(--font-mono);
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-bottom: 1.5rem;
}}
.footer {{
  background: var(--text-primary);
  color: var(--bg-secondary);
  padding: 1rem 1.5rem;
  margin-top: auto;
  text-align: center;
  font-family: var(--font-mono);
  font-size: 0.75rem;
}}
@media (max-width: 768px) {{
  .header-content {{ flex-direction: column; gap: 1rem; }}
  .page-title, .post-title {{ font-size: 1.5rem; }}
  .posts-grid {{ grid-template-columns: 1fr; }}
  .content {{ padding: 1rem; }}
  .nav {{ flex-wrap: wrap; justify-content: center; }}
}}
  </style>
</head>
<body>
  <div class="migration-banner" id="migrationBanner">
    Novo site! Migramos do Google Sites para cá.
    <button class="close-banner" onclick="document.getElementById('migrationBanner').style.display='none';localStorage.setItem('bannerClosed','1');">×</button>
  </div>
  <script>if(localStorage.getItem('bannerClosed')==='1')document.getElementById('migrationBanner').style.display='none';</script>
  <header class="header">
    <div class="header-content">
      <a href="{base_url}index.html" class="logo">
        <span class="logo-bracket">[</span>IA+EDU<span class="logo-bracket">]</span>
      </a>
      <nav class="nav">
        <a href="{base_url}index.html">Resumos</a>
        <span class="nav-separator">//</span>
        <a href="{base_url}links.html">Links</a>
      </nav>
    </div>
  </header>
  <main class="main">
    {content}
  </main>
  <footer class="footer">
    Aprendizados_IA+Educação // Resumos gerados com LLM // {year}<br>
    <span style="opacity: 0.7;">Feito por Marina e Tiago Maluta</span>
  </footer>
  {scripts}
</body>
</html>
"""

# JavaScript para busca com índice completo
SEARCH_SCRIPT_INDEX = """
<script>
(function() {{
  // Calcula e exibe "X dias atrás" nos cards
  document.querySelectorAll('.post-card-footer[data-end-date]').forEach(footer => {{
    const endDate = new Date(footer.dataset.endDate);
    const today = new Date();
    const diffTime = today - endDate;
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    if (diffDays >= 0) {{
      const span = document.createElement('span');
      span.style.color = '#9ca3af';
      span.textContent = ` (~ ${{diffDays}} dias atrás)`;
      footer.appendChild(span);
    }}
  }});

  let searchIndex = null;
  const searchInput = document.getElementById('searchInput');
  const searchResults = document.getElementById('searchResults');
  const postsGrid = document.getElementById('postsGrid');
  const searchStats = document.getElementById('searchStats');
  const noResults = document.getElementById('noResults');

  if (!searchInput) return;

  // Carrega o índice de busca
  fetch('{base_url}search-index.json')
    .then(r => r.json())
    .then(data => {{
      searchIndex = data;
      searchStats.textContent = `${{data.length}} resumos disponíveis para busca`;
    }})
    .catch(err => console.error('Erro ao carregar índice:', err));

  // Função para criar snippet com highlight
  function createSnippet(text, query, maxLen = 200) {{
    const lowerText = text.toLowerCase();
    const lowerQuery = query.toLowerCase();
    const idx = lowerText.indexOf(lowerQuery);

    if (idx === -1) return text.slice(0, maxLen) + '...';

    // Pega contexto ao redor do match
    const start = Math.max(0, idx - 60);
    const end = Math.min(text.length, idx + query.length + 100);
    let snippet = (start > 0 ? '...' : '') + text.slice(start, end) + (end < text.length ? '...' : '');

    // Faz highlight (case-insensitive)
    const regex = new RegExp(`(${{query.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&')}})`, 'gi');
    snippet = snippet.replace(regex, '<mark>$1</mark>');

    return snippet;
  }}

  // Função de busca
  function search(query) {{
    if (!searchIndex || query.length < 2) {{
      searchResults.classList.remove('active');
      searchResults.innerHTML = '';
      postsGrid.classList.remove('hidden');
      noResults.classList.remove('active');
      searchStats.textContent = `${{searchIndex ? searchIndex.length : 0}} resumos disponíveis para busca`;
      return;
    }}

    const lowerQuery = query.toLowerCase();
    const results = [];

    searchIndex.forEach(item => {{
      const contentLower = item.content.toLowerCase();
      const titleLower = item.title.toLowerCase();

      // Conta ocorrências para ranking
      let score = 0;
      if (titleLower.includes(lowerQuery)) score += 10;

      let idx = 0;
      while ((idx = contentLower.indexOf(lowerQuery, idx)) !== -1) {{
        score += 1;
        idx += lowerQuery.length;
      }}

      if (score > 0) {{
        results.push({{ ...item, score }});
      }}
    }});

    // Ordena por relevância
    results.sort((a, b) => b.score - a.score);

    if (results.length === 0) {{
      searchResults.classList.remove('active');
      searchResults.innerHTML = '';
      postsGrid.classList.add('hidden');
      noResults.classList.add('active');
      searchStats.textContent = `Nenhum resultado para "${{query}}"`;
      return;
    }}

    // Renderiza resultados
    postsGrid.classList.add('hidden');
    noResults.classList.remove('active');
    searchStats.textContent = `${{results.length}} resultado(s) para "${{query}}"`;

    let html = '';
    results.slice(0, 20).forEach(item => {{
      const snippet = createSnippet(item.content, query);
      html += `
        <a href="${{item.url}}" class="search-result-item">
          <div class="search-result-title">${{item.title}}</div>
          <div class="search-result-meta">Semana: ${{item.week}}</div>
          <div class="search-result-snippet">${{snippet}}</div>
        </a>
      `;
    }});

    searchResults.innerHTML = html;
    searchResults.classList.add('active');
  }}

  // Debounce para não buscar a cada tecla
  let debounceTimer;
  searchInput.addEventListener('input', function() {{
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => search(this.value.trim()), 150);
  }});

  // Limpa busca com Escape
  searchInput.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') {{
      this.value = '';
      search('');
    }}
  }});
}})();
</script>
"""

# JavaScript para busca simples na página de links
SEARCH_SCRIPT_LINKS = """
<script>
(function() {
  const searchInput = document.getElementById('searchInput');
  const items = document.querySelectorAll('[data-searchable]');
  const sections = document.querySelectorAll('.links-section');
  const statsEl = document.getElementById('searchStats');
  const noResults = document.getElementById('noResults');

  if (!searchInput) return;

  searchInput.addEventListener('input', function() {
    const query = this.value.toLowerCase().trim();
    let visible = 0;

    items.forEach(item => {
      const text = item.dataset.searchable.toLowerCase();
      const matches = query === '' || text.includes(query);
      item.classList.toggle('hidden', !matches);
      if (matches) visible++;
    });

    // Esconde seções vazias
    sections.forEach(section => {
      const visibleItems = section.querySelectorAll('.link-item:not(.hidden)').length;
      section.style.display = visibleItems === 0 ? 'none' : 'block';
    });

    if (statsEl) {
      statsEl.textContent = query ? `${visible} resultado(s) para "${this.value}"` : `${items.length} links`;
    }
    if (noResults) {
      noResults.classList.toggle('active', visible === 0);
    }
  });

  if (statsEl) statsEl.textContent = `${items.length} links`;
})();
</script>
"""


def extract_dates_from_filename(filename: str) -> tuple[str, str, str] | None:
    """Extrai datas do nome do arquivo."""
    pattern = r"resumo_semana_(\d{4})-(\d{2})-(\d{2})_(\d{4})-(\d{2})-(\d{2})\.md"
    match = re.match(pattern, filename)
    if match:
        start = f"{match.group(3)}/{match.group(2)}/{match.group(1)}"
        end = f"{match.group(6)}/{match.group(5)}/{match.group(4)}"
        slug = f"{match.group(4)}-{match.group(5)}-{match.group(6)}"
        return start, end, slug
    return None


def extract_excerpt(content: str, max_len: int = 280) -> str:
    """Extrai o sumário executivo como excerpt com limite de caracteres."""
    match = re.search(r"## Sumário Executivo[^\n]*\n\n(.+?)(?:\n\n##|\Z)", content, re.DOTALL)
    if match:
        excerpt = match.group(1).strip().replace("\n", " ")
        if len(excerpt) > max_len:
            excerpt = excerpt[:max_len - 3].rsplit(" ", 1)[0] + "..."
        return excerpt
    return "Resumo semanal do grupo IA + Educação."


def extract_links(content: str) -> list[dict]:
    """Extrai todos os links markdown do conteúdo."""
    links = []
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    for match in re.finditer(pattern, content):
        title = match.group(1).strip()
        url = match.group(2).strip()
        if url.startswith('http'):
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.replace('www.', '')
                # Se o título é uma URL, tenta criar um título melhor
                if title.startswith('http') or title == url:
                    # Extrai path e tenta criar título legível
                    path = parsed.path.strip('/')
                    if path:
                        # Pega última parte do path e formata
                        slug = path.split('/')[-1]
                        # Remove extensões e parâmetros
                        slug = re.sub(r'\.[a-z]+$', '', slug)
                        slug = re.sub(r'[-_]', ' ', slug)
                        if len(slug) > 5:
                            title = f"{domain.split('.')[0].title()} - {slug[:60]}"
                        else:
                            title = domain.title()
                    else:
                        title = domain.title()
            except Exception:
                domain = 'link'
            links.append({
                'title': title,
                'url': url,
                'domain': domain
            })
    return links


def clean_text_for_search(text: str) -> str:
    """Limpa texto para indexação de busca."""
    # Remove markdown links mantendo o texto
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove formatação markdown
    text = re.sub(r'[*_`#>-]', ' ', text)
    # Normaliza espaços
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_month_name(month: str) -> str:
    """Retorna nome do mês em português."""
    months = {
        "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
        "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
        "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro"
    }
    return months.get(month, month)


def build_post(md_path: Path, output_dir: Path, base_url: str) -> dict | None:
    """Converte um markdown em HTML e retorna metadados."""
    dates = extract_dates_from_filename(md_path.name)
    if not dates:
        print(f"Aviso: Ignorando {md_path.name}", file=sys.stderr)
        return None

    week_start, week_end, slug = dates
    content = md_path.read_text(encoding="utf-8")

    links = extract_links(content)

    # Remove cabeçalho original
    lines = content.split("\n")
    start_idx = next((i for i, line in enumerate(lines) if line.startswith("## Sumário")), 0)
    clean_content = "\n".join(lines[start_idx:])

    # Converte markdown para HTML
    md = markdown.Markdown(extensions=["tables", "fenced_code"])
    html_content = md.convert(clean_content)

    # Metadados
    title = "Resumo Semanal"
    excerpt = extract_excerpt(content)

    # Texto limpo para busca (conteúdo completo)
    search_content = clean_text_for_search(clean_content)

    post_content = f"""
    <a href="{base_url}index.html" class="back-link">Voltar aos resumos</a>
    <header class="post-header">
      <div class="post-meta">
        <span class="post-category">Resumo Semanal</span>
        <span class="post-date">{week_end}</span>
      </div>
      <h1 class="post-title">{title}</h1>
      <p class="post-week">Semana: {week_start} → {week_end}</p>
    </header>
    <article class="content">
      {html_content}
    </article>
    """

    page_html = BASE_TEMPLATE.format(
        title=title,
        description=excerpt,
        base_url=base_url,
        content=post_content,
        year=datetime.now().year,
        scripts=""
    )

    output_path = output_dir / f"{slug}.html"
    output_path.write_text(page_html, encoding="utf-8")

    return {
        "title": title,
        "slug": slug,
        "week_start": week_start,
        "week_end": week_end,
        "excerpt": excerpt,
        "date": slug,
        "links": links,
        "search_content": search_content,
    }


def build_search_index(posts: list[dict], output_dir: Path, base_url: str) -> None:
    """Gera o índice JSON para busca."""
    index = []
    for post in posts:
        index.append({
            "title": post["title"],
            "url": f"{base_url}{post['slug']}.html",
            "week": f"{post['week_start']} → {post['week_end']}",
            "content": post["search_content"],
        })

    index_path = output_dir / "search-index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=None), encoding="utf-8")


def build_index(posts: list[dict], output_dir: Path, base_url: str) -> None:
    """Gera a página índice."""
    posts = sorted(posts, key=lambda p: p["date"], reverse=True)

    cards_html = ""
    for post in posts:
        share_url = f"{base_url}{post['slug']}.html"
        title_js = post['title'].replace("'", "\\'")
        # Converte data DD/MM/YYYY para YYYY-MM-DD para JavaScript
        end_parts = post['week_end'].split('/')
        end_date_iso = f"{end_parts[2]}-{end_parts[1]}-{end_parts[0]}"
        cards_html += f"""
        <div class="post-card">
          <div class="post-card-header">
            <span class="post-card-category">Resumo</span>
            <span class="post-card-action" onclick="event.stopPropagation(); window.open('https://wa.me/?text=' + encodeURIComponent('{title_js} - ' + window.location.origin + '/{share_url}'), '_blank')">📤 Compartilhar</span>
          </div>
          <a href="{base_url}{post['slug']}.html" style="text-decoration: none; color: inherit;">
            <div class="post-card-image">🖼️ imagem gerada por IA</div>
            <h2 class="post-card-title">{post['title']}</h2>
            <p class="post-card-excerpt">{post['excerpt']}</p>
          </a>
          <div class="post-card-footer" data-end-date="{end_date_iso}">{post['week_start']} → {post['week_end']}</div>
        </div>
        """

    index_content = f"""
    <header class="page-header">
      <h1 class="page-title">RESUMOS_SEMANAIS</h1>
      <p class="page-subtitle">Grupo "Aprendizados IA + Educação" // Sínteses geradas via LLM</p>
    </header>
    <div class="search-container">
      <input type="text" id="searchInput" class="search-input" placeholder="Buscar em todos os resumos... (ex: Educação, NotebookLM, Matemática)">
      <div id="searchStats" class="search-stats">Carregando índice...</div>
    </div>
    <div id="searchResults" class="search-results"></div>
    <div id="noResults" class="no-results">Nenhum resultado encontrado. Tente outros termos.</div>
    <div id="postsGrid" class="posts-grid">
      {cards_html}
    </div>
    """

    page_html = BASE_TEMPLATE.format(
        title="Resumos Semanais",
        description="Resumos semanais do grupo WhatsApp sobre IA e Educação",
        base_url=base_url,
        content=index_content,
        year=datetime.now().year,
        scripts=SEARCH_SCRIPT_INDEX.format(base_url=base_url)
    )

    (output_dir / "index.html").write_text(page_html, encoding="utf-8")


def load_links_from_json(path: Path) -> list[dict]:
    """Carrega links do arquivo JSON extraído pelo extract_links.py."""
    if not path.exists():
        print(f"Aviso: {path} não encontrado", file=sys.stderr)
        return []

    data = json.loads(path.read_text(encoding="utf-8"))

    # Normaliza formato para o esperado pelo build_links_page
    links = []
    for item in data:
        links.append({
            "url": item["url"],
            "title": item.get("title", item["domain"]),
            "domain": item["domain"],
            "week": item.get("date", ""),  # data no formato DD/MM/YYYY
            "shared_by": item.get("shared_by", ""),
        })
    return links


def build_links_page(
    posts: list[dict],
    output_dir: Path,
    base_url: str,
    links_source: str = "resumos",
    links_json_path: Path | None = None,
) -> int:
    """Gera a página de links.

    Args:
        posts: Lista de posts processados
        output_dir: Diretório de saída
        base_url: URL base do site
        links_source: Fonte dos links - "resumos", "full" ou "both"
        links_json_path: Caminho para o JSON de links (usado com "full" ou "both")
    """
    links_by_domain: dict[str, list[dict]] = defaultdict(list)
    seen_urls = set()

    # Carrega links dos resumos (fonte original)
    if links_source in ("resumos", "both"):
        for post in sorted(posts, key=lambda p: p["date"], reverse=True):
            for link in post.get("links", []):
                if link["url"] not in seen_urls:
                    seen_urls.add(link["url"])
                    link["week"] = post["week_end"]
                    link["post_slug"] = post["slug"]
                    links_by_domain[link["domain"]].append(link)

    # Carrega links do JSON completo
    if links_source in ("full", "both"):
        json_path = links_json_path or Path("links/links.json")
        external_links = load_links_from_json(json_path)
        for link in external_links:
            if link["url"] not in seen_urls:
                seen_urls.add(link["url"])
                links_by_domain[link["domain"]].append(link)

    sorted_domains = sorted(links_by_domain.items(), key=lambda x: -len(x[1]))
    total_links = len(seen_urls)

    sections_html = ""
    for domain, links in sorted_domains:
        links_html = ""
        for link in links:
            title_safe = html.escape(link["title"])
            title_js = html.escape(link["title"]).replace("'", "\\'").replace("(", "\\(").replace(")", "\\)")
            # Escape special chars in URL for JavaScript
            url_js = link["url"].replace("'", "\\'").replace("(", "%28").replace(")", "%29")
            searchable = f"{link['title']} {link['domain']} {link['week']}"
            links_html += f"""
            <div class="link-item" data-searchable="{html.escape(searchable)}" onclick="window.open('{url_js}', '_blank')" style="cursor: pointer;">
              <div class="link-header">
                <span class="link-domain">{link['domain']}</span>
                <span class="link-action" onclick="event.stopPropagation(); window.open('https://wa.me/?text=' + encodeURIComponent('{title_js} {url_js}'), '_blank')">📤 Compartilhar</span>
              </div>
              <div class="link-title">{title_safe}</div>
              <div class="link-qr">📱 QR Code</div>
              <div class="link-footer">
                <span>Semana: {link['week']}</span>
                <span style="color: var(--accent-blue);">↗ Abrir</span>
              </div>
            </div>
            """

        sections_html += f"""
        <section class="links-section">
          <h2 class="links-section-title">{domain} ({len(links)})</h2>
          <div class="links-grid">
            {links_html}
          </div>
        </section>
        """

    links_content = f"""
    <header class="page-header">
      <h1 class="page-title">REPOSITÓRIO_DE_LINKS</h1>
      <p class="page-subtitle">Todos os links compartilhados no grupo, organizados por fonte</p>
    </header>
    <div class="search-container">
      <input type="text" id="searchInput" class="search-input" placeholder="Filtrar links...">
      <div id="searchStats" class="search-stats"></div>
    </div>
    <p class="links-count">{total_links} links únicos de {len(sorted_domains)} fontes</p>
    {sections_html}
    <div id="noResults" class="no-results">Nenhum link encontrado</div>
    """

    page_html = BASE_TEMPLATE.format(
        title="Repositório de Links",
        description="Links sobre IA e Educação compartilhados no grupo",
        base_url=base_url,
        content=links_content,
        year=datetime.now().year,
        scripts=SEARCH_SCRIPT_LINKS
    )

    (output_dir / "links.html").write_text(page_html, encoding="utf-8")
    return total_links


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input_dir", type=Path, default=Path("resumos"))
    parser.add_argument("--output_dir", type=Path, default=Path("docs"))
    parser.add_argument("--base_url", default="")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument(
        "--links-source",
        choices=["resumos", "full", "both"],
        default="resumos",
        help="Fonte dos links: resumos (extrai do markdown), full (usa JSON), both (combina ambos)",
    )
    parser.add_argument(
        "--links-json",
        type=Path,
        default=Path("links/links.json"),
        help="Caminho para o JSON de links (usado com --links-source full ou both)",
    )
    args = parser.parse_args()

    if not args.input_dir.exists():
        print(f"Erro: {args.input_dir} não encontrado", file=sys.stderr)
        return 2

    if args.clean and args.output_dir.exists():
        shutil.rmtree(args.output_dir)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(args.input_dir.glob("resumo_semana_*.md"))
    if not md_files:
        print(f"Nenhum resumo em {args.input_dir}", file=sys.stderr)
        return 1

    posts = []
    for md_path in md_files:
        post = build_post(md_path, args.output_dir, args.base_url)
        if post:
            posts.append(post)
            print(f"Gerado: {post['slug']}.html")

    build_search_index(posts, args.output_dir, args.base_url)
    print("Gerado: search-index.json")

    build_index(posts, args.output_dir, args.base_url)
    print("Gerado: index.html")

    total_links = build_links_page(
        posts,
        args.output_dir,
        args.base_url,
        links_source=args.links_source,
        links_json_path=args.links_json,
    )
    print(f"Gerado: links.html ({total_links} links, fonte: {args.links_source})")

    print(f"\n{len(posts) + 2} páginas + índice em {args.output_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
