#!/usr/bin/env python3
"""
Marquez Advogados — Atualizador automático de notícias
Busca artigos do STJ, Conjur, Migalhas e Jota e atualiza o index.html
"""

import urllib.request
import xml.etree.ElementTree as ET
import re
import os
import json
from datetime import datetime, timezone
from html import unescape

# ── Configuração ──────────────────────────────────────────────────────────────

FEEDS = [
    {
        "nome": "STJ",
        "url": "https://processo.stj.jus.br/jurisprudencia/externo/InformativoFeed",
        "label": "STJ — Informativo",
    },
    {
        "nome": "Conjur",
        "url": "https://www.conjur.com.br/feed/",
        "label": "Conjur",
    },
    {
        "nome": "Migalhas",
        "url": "https://www.migalhas.com.br/rss/quentes",
        "label": "Migalhas",
    },
    {
        "nome": "Jota",
        "url": "https://www.jota.info/feed",
        "label": "Jota",
    },
]

# Palavras-chave para filtrar artigos relevantes para as áreas do escritório
KEYWORDS = [
    # Societário
    "societário", "societaria", "sócio", "socios", "dissolução", "haveres",
    "acordo de sócios", "joint venture", "fusão", "aquisição", "m&a",
    "reestruturação", "due diligence", "governança",
    # Contratos
    "contrato", "contratos", "cláusula", "inadimplemento", "rescisão",
    "take or pay", "mútuo", "fornecimento", "distribuição",
    # Imobiliário
    "imobiliário", "imóvel", "imóveis", "distrato", "incorporação",
    "alienação fiduciária", "locação", "built to suit", "leilão",
    # Família e Sucessões
    "sucessão", "inventário", "herança", "holding familiar", "testamento",
    "planejamento patrimonial", "partilha",
    # Contencioso / Tribunais
    "stj", "stf", "tribunal superior", "recurso especial", "recurso extraordinário",
    "agência reguladora", "anatel", "aneel", "anvisa", "cade",
    "arbitragem", "mediação", "litígio",
    # Terceiro Setor
    "incentivo fiscal", "lei rouanet", "terceiro setor", "ong", "impacto social",
    # Geral empresarial
    "empresarial", "empresas", "código civil", "reforma", "lgpd",
    "compliance", "anticorrupção", "regulatório",
]

MAX_NOTICIAS = 6
MESES_PT = {
    "Jan": "Jan", "Feb": "Fev", "Mar": "Mar", "Apr": "Abr",
    "May": "Mai", "Jun": "Jun", "Jul": "Jul", "Aug": "Ago",
    "Sep": "Set", "Oct": "Out", "Nov": "Nov", "Dec": "Dez",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def formatar_data(data_str):
    """Converte data RSS para formato 'Mmm YYYY' em português."""
    formatos = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ]
    for fmt in formatos:
        try:
            dt = datetime.strptime(data_str.strip(), fmt)
            mes_en = dt.strftime("%b")
            mes_pt = MESES_PT.get(mes_en, mes_en)
            return f"{mes_pt} {dt.year}"
        except ValueError:
            continue
    return datetime.now().strftime("Abr %Y")

def limpar_html(texto):
    """Remove tags HTML e limpa o texto."""
    if not texto:
        return ""
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = unescape(texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def truncar(texto, max_chars=160):
    """Trunca texto preservando palavras completas."""
    if len(texto) <= max_chars:
        return texto
    return texto[:max_chars].rsplit(' ', 1)[0].rstrip('.,;:') + '…'

def e_relevante(titulo, descricao=""):
    """Verifica se o artigo é relevante para as áreas do escritório."""
    texto = (titulo + " " + descricao).lower()
    # Remove acentos para comparação
    texto = (texto.replace('ã', 'a').replace('ç', 'c').replace('é', 'e')
             .replace('ê', 'e').replace('ó', 'o').replace('ú', 'u')
             .replace('á', 'a').replace('í', 'i'))
    for kw in KEYWORDS:
        kw_norm = (kw.lower().replace('ã', 'a').replace('ç', 'c')
                   .replace('é', 'e').replace('ê', 'e').replace('ó', 'o')
                   .replace('ú', 'u').replace('á', 'a').replace('í', 'i'))
        if kw_norm in texto:
            return True
    return False

def buscar_feed(feed):
    """Busca e parseia um feed RSS, retorna lista de artigos."""
    artigos = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; MarquezAdvogados/1.0)',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
    }
    try:
        req = urllib.request.Request(feed["url"], headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read()

        root = ET.fromstring(xml_data)
        # Suporte a RSS 2.0 e Atom
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        items = root.findall('.//item') or root.findall('.//atom:entry', ns)

        for item in items[:20]:  # Analisa os 20 mais recentes
            def get(tag, atom_tag=None):
                el = item.find(tag)
                if el is None and atom_tag:
                    el = item.find(atom_tag, ns)
                if el is not None and el.text:
                    return el.text.strip()
                # Tenta CDATA
                if el is not None:
                    return (el.text or "").strip()
                return ""

            titulo = limpar_html(get('title', 'atom:title'))
            link = get('link', 'atom:link')
            if not link:
                link_el = item.find('atom:link', ns)
                if link_el is not None:
                    link = link_el.get('href', '')
            descricao = limpar_html(get('description') or get('summary', 'atom:summary'))
            data_str = get('pubDate') or get('published', 'atom:published') or get('updated', 'atom:updated')
            data = formatar_data(data_str) if data_str else datetime.now().strftime("Abr %Y")

            if not titulo or not link:
                continue

            if e_relevante(titulo, descricao):
                artigos.append({
                    "titulo": titulo,
                    "link": link,
                    "descricao": truncar(descricao) if descricao else "",
                    "data": data,
                    "fonte": feed["label"],
                    "nome": feed["nome"],
                })

        print(f"  ✓ {feed['nome']}: {len(artigos)} artigos relevantes encontrados")

    except Exception as e:
        print(f"  ✗ {feed['nome']}: erro — {e}")

    return artigos

def gerar_card(artigo, idx):
    """Gera o HTML de um card de notícia."""
    desc_html = f'\n        <p class="news-desc">{artigo["descricao"]}</p>' if artigo["descricao"] else ""
    return f"""      <div class="news-card rv">
        <div class="news-src">{artigo["fonte"]} &mdash; {artigo["data"]}</div>
        <h3 class="news-title">{artigo["titulo"]}</h3>{desc_html}
        <a href="{artigo["link"]}" target="_blank" rel="noopener" class="news-link">Ler artigo <svg viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg></a>
      </div>"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(f"Marquez Advogados — Atualizador de Notícias")
    print(f"Executado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)

    # Buscar artigos de todas as fontes
    todos = []
    for feed in FEEDS:
        print(f"\nBuscando {feed['nome']}...")
        artigos = buscar_feed(feed)
        todos.extend(artigos)

    # Se não houver artigos suficientes, manter os existentes
    if len(todos) < 3:
        print(f"\n⚠ Poucos artigos encontrados ({len(todos)}). Mantendo notícias atuais.")
        return

    # Selecionar os melhores: distribuir entre fontes quando possível
    selecionados = []
    por_fonte = {}
    for a in todos:
        por_fonte.setdefault(a["nome"], []).append(a)

    # Pega até 2 de cada fonte, priorizando variedade
    for _ in range(2):
        for fonte in ["STJ", "Conjur", "Migalhas", "Jota"]:
            if fonte in por_fonte and por_fonte[fonte] and len(selecionados) < MAX_NOTICIAS:
                selecionados.append(por_fonte[fonte].pop(0))

    # Completa com o que restar se necessário
    restantes = [a for fonte in por_fonte.values() for a in fonte]
    while len(selecionados) < MAX_NOTICIAS and restantes:
        selecionados.append(restantes.pop(0))

    print(f"\n✓ {len(selecionados)} notícias selecionadas:")
    for a in selecionados:
        print(f"  [{a['nome']}] {a['titulo'][:70]}...")

    # Ler index.html
    html_path = "index.html"
    if not os.path.exists(html_path):
        print(f"\n✗ {html_path} não encontrado!")
        return

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Gerar novo bloco de cards
    novos_cards = "\n".join(gerar_card(a, i) for i, a in enumerate(selecionados))

    # Substituir a news-grid existente
    pattern = r'(<div class="news-grid">)\s*.*?\s*(</div>\s*</div>\s*</section>\s*<div class="nl-bar)'
    replacement = f'\\1\n{novos_cards}\n    \\2'
    novo_html, n = re.subn(pattern, replacement, html, flags=re.DOTALL)

    if n == 0:
        print("\n✗ Não foi possível localizar a seção de notícias no HTML.")
        return

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(novo_html)

    print(f"\n✓ index.html atualizado com sucesso!")
    print(f"  Notícias: {len(selecionados)} | Fontes: {set(a['nome'] for a in selecionados)}")

    # Salvar log
    log = {
        "ultima_atualizacao": datetime.now(timezone.utc).isoformat(),
        "noticias": len(selecionados),
        "fontes": list(set(a["nome"] for a in selecionados)),
    }
    with open("scripts/ultimo_log.json", "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
