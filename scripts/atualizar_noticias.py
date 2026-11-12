#!/usr/bin/env python3
"""
Marquez Advogados — Atualizador automático de notícias
Fontes: Conjur (RSS), Migalhas (HTML), Jota (RSS)
Roda toda terça-feira às 20h (horário de Brasília = 23h UTC)
"""

import urllib.request
import xml.etree.ElementTree as ET
import re, os, json
from datetime import datetime, timezone
from html import unescape

# ---------------------------------------------------------------------------
# Fontes RSS
# ---------------------------------------------------------------------------
FEEDS_RSS = [
    {"nome":"Conjur", "url":"https://www.conjur.com.br/feed/", "label":"Conjur"},
    {"nome":"Jota",   "url":"https://www.jota.info/feed",      "label":"Jota"},
]

# URLs de scraping do Migalhas (sem RSS) — quentes pág 1 e 2 + depeso
MIGALHAS_URLS = [
    "https://www.migalhas.com.br/quentes",
    "https://www.migalhas.com.br/quentes?pagina=2",
    "https://www.migalhas.com.br/depeso",
]

# ---------------------------------------------------------------------------
# Keywords das áreas de atuação do escritório
#
# NOTA: matching por substring — "contrato" captura também "contratação",
# "contratual", "contratante", etc. As palavras que geravam falso positivo
# ("guarda", "cisão") foram removidas como termo solo e mantidas apenas
# em expressões compostas ("guarda de bens", "cisão societária").
# ---------------------------------------------------------------------------

KEYWORDS = [
    # --- ESCRITÓRIO E ADVOGADO ---
    "Rafael Marquez","Rafael Batista Marquez","Rafael B. Marquez",
    "Marquez Advogados",

    # --- CONTRATOS ---
    "contrato","contratual","contrato comercial","contrato empresarial",
    "contrato de compra e venda","contrato de locacao",
    "contrato de prestacao de servicos","contrato de distribuicao",
    "contrato de fornecimento","opcao de compra","stock option",
    "contrato de investimento","mutuo conversivel","take or pay",
    "joint venture","consorcio","parceria empresarial",
    "inadimplemento contratual","rescisao contratual","revisao contratual",
    "quebra contratual","inexecucao contratual","penalidade contratual",
    "clausula contratual","distrato","negociacao contratual",

    # --- IMOBILIARIO E CONSTRUCAO ---
    "imovel","imobiliario","imobiliaria","locatario","locador",
    "aquisicao de imovel","incorporacao imobiliaria","incorporadora",
    "built to suit","construcao civil","construtora",
    "dispute board","alienacao fiduciaria",
    "leilao judicial","leilao extrajudicial","distrato imobiliario",
    "despejo","retomada de imovel","due diligence imobiliaria",
    "regularizacao fundiaria","condominio","compra e venda de imovel",
    "multipropriedade","loteamento",

    # --- PRE-LITIGIO E RESOLUCAO DE DISPUTAS ---
    "mediacao","mediador","camara de mediacao","conciliacao",
    "arbitragem","arbitro","camara de arbitragem","tribunal arbitral",
    "clausula compromissoria","compromisso arbitral","sentenca arbitral",
    "acordo extrajudicial","resolucao de disputas","resolucao de conflitos",
    "pre-litigio","prevencao de litigio",

    # --- FAMILIA, SUCESSOES E INVENTARIOS ---
    "inventario","heranca","espolio","partilha","testamento",
    "planejamento sucessorio","planejamento patrimonial","sucessao",
    "holding familiar","holding patrimonial","doacao","meacao",
    "divorcio","uniao estavel","regime de bens",
    "direito de familia","curatela","tutela",
    "guarda de bens","guarda de menores","guarda compartilhada",
    "disputa familiar","litigio familiar","transmissao de patrimonio",

    # --- DISPUTAS SOCIETARIAS ---
    "disputa societaria","litigio societario","contencioso societario",
    "apuracao de haveres","dissolucao de sociedade","dissolucao parcial",
    "exclusao de socio","retirada de socio","acordo de socios",
    "conflito entre socios","desconsideracao da personalidade juridica",
    "societario","direito societario","governanca corporativa",
    "reestruturacao societaria","aquisicao de participacao",
    "due diligence","m&a","fusao","aquisicao de empresa",
    "cisao societaria","cisao de empresa","incorporacao societaria",

    # --- DISPUTAS CONTRATUAIS E IMOBILIARIAS ---
    "disputa contratual","litigio contratual","inadimplemento",
    "disputa imobiliaria","reintegracao de posse","acao possessoria","usucapiao",

    # --- RESPONSABILIDADE CIVIL ---
    "responsabilidade civil","indenizacao","reparacao de danos",
    "responsabilidade contratual","dano moral","dano material",
    "dano emergente","lucro cessante","perda de chance",

    # --- RECUPERACAO JUDICIAL ---
    "recuperacao judicial","recuperacao extrajudicial","falencia",
    "plano de recuperacao","assembleia de credores",

    # --- QUESTOES REGULATORIAS ---
    "regulatorio","regulatoria","regulacao","regulador",
    "agencia reguladora","anatel","aneel","anp","anvisa","antaq","antf",
    "cvm","bacen","banco central",
    "compliance","licenciamento","autorizacao regulatoria",
    "infracao regulatoria","processo administrativo","auto de infracao",
]

# ---------------------------------------------------------------------------

MAX_NOTICIAS = 6
FONTES_ORDEM = ["Conjur", "Migalhas", "Jota"]

MESES_PT = {"Jan":"Jan","Feb":"Fev","Mar":"Mar","Apr":"Abr","May":"Mai","Jun":"Jun",
            "Jul":"Jul","Aug":"Ago","Sep":"Set","Oct":"Out","Nov":"Nov","Dec":"Dez"}
HEADERS = {"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0 Safari/537.36",
           "Accept":"text/html,application/xml,*/*","Accept-Language":"pt-BR,pt;q=0.9"}

def normalizar(t):
    return t.lower().translate(str.maketrans('ãáàâäçéêëíîïóôõöúûüý',
                                             'aaaaceeeiiiooooouuuy'))

def formatar_data(s):
    for fmt in ["%a, %d %b %Y %H:%M:%S %z","%a, %d %b %Y %H:%M:%S GMT",
                "%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%SZ","%Y-%m-%d","%d/%m/%Y"]:
        try:
            dt = datetime.strptime(s.strip(), fmt)
            return f"{MESES_PT.get(dt.strftime('%b'),dt.strftime('%b'))} {dt.year}"
        except: pass
    return datetime.now().strftime("%b %Y")

def limpar(t):
    if not t: return ""
    return re.sub(r'\s+',' ',unescape(re.sub(r'<[^>]+>',' ',t))).strip()

def truncar(t, n=165):
    return t if len(t) <= n else t[:n].rsplit(' ',1)[0].rstrip('.,;:')+'\u2026'

def e_relevante(titulo, desc=""):
    """
    Verifica se o artigo é relevante para as áreas de atuação do escritório.
    Usa matching por substring após normalização (sem acento, minúsculas).
    Palavras problemáticas ('guarda', 'cisão') só existem em formas compostas
    na lista de keywords, evitando falsos positivos.
    """
    txt = normalizar(titulo + " " + desc)
    matched = [k for k in KEYWORDS if normalizar(k) in txt]
    if matched:
        print(f"    → match: {matched[:3]}")
    return len(matched) > 0

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

# ---------------------------------------------------------------------------
# Busca RSS (Conjur, Jota)
# ---------------------------------------------------------------------------
def buscar_rss(feed):
    artigos = []
    try:
        root = ET.fromstring(fetch(feed["url"]))
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        items = root.findall('.//item') or root.findall('.//a:entry', ns)
        for it in items[:30]:
            def g(tag, at=None):
                el = it.find(tag)
                if el is None and at:
                    el = it.find(at, ns)
                return (el.text or "").strip() if el is not None else ""

            titulo = limpar(g('title', 'a:title'))
            link_el = it.find('link') or it.find('a:link', ns)
            link = ""
            if link_el is not None:
                link = (link_el.text or link_el.get('href', '')).strip()
            desc = limpar(g('description') or g('summary', 'a:summary'))
            data = formatar_data(
                g('pubDate') or g('published', 'a:published') or g('updated', 'a:updated')
            )
            if titulo and link:
                print(f"  Checando: {titulo[:70]}...")
                if e_relevante(titulo, desc):
                    artigos.append({
                        "titulo": titulo, "link": link, "descricao": truncar(desc),
                        "data": data, "fonte": feed["label"], "nome": feed["nome"]
                    })
        print(f"  ✓ {feed['nome']}: {len(artigos)} relevantes de {min(len(items),30)} verificados")
    except Exception as e:
        print(f"  ✗ {feed['nome']}: {e}")
    return artigos

# ---------------------------------------------------------------------------
# Busca HTML do Migalhas (sem RSS)
# ---------------------------------------------------------------------------
def _scrape_migalhas_pagina(url_pagina, seen):
    """Raspa uma página do Migalhas e retorna artigos encontrados (sem duplicatas)."""
    artigos = []
    try:
        raw = fetch(url_pagina).decode('utf-8', errors='replace')
        anchor_re = re.compile(r'<a\s([^>]{5,500})>', re.IGNORECASE | re.DOTALL)

        for m in anchor_re.finditer(raw):
            attrs = m.group(1)
            # Aceita links de /quentes/DIGITS/ ou /depeso/DIGITS/
            href_m = re.search(
                r'href="([^"]*(?:quentes|depeso)/\d+/[^"#?]+)"', attrs, re.IGNORECASE
            )
            if not href_m:
                continue

            url = href_m.group(1)
            if url.startswith('/'):
                url = 'https://www.migalhas.com.br' + url
            if url in seen:
                continue
            seen.add(url)

            # Título: prefere atributo title=, senão deriva do slug
            title_m = re.search(r'title="([^"]{10,})"', attrs, re.IGNORECASE)
            if title_m:
                titulo = limpar(title_m.group(1))
            else:
                slug = url.split('/')[-1]
                titulo = slug.replace('-', ' ').capitalize()

            if len(titulo) < 15:
                continue

            print(f"  Checando: {titulo[:70]}...")
            if e_relevante(titulo):
                artigos.append({
                    "titulo": titulo, "link": url, "descricao": "",
                    "data": datetime.now().strftime("%b %Y"),
                    "fonte": "Migalhas", "nome": "Migalhas"
                })

    except Exception as e:
        print(f"  ⚠ Erro em {url_pagina}: {e}")
    return artigos


def buscar_migalhas():
    artigos = []
    seen = set()
    total_verificados = 0

    for pagina_url in MIGALHAS_URLS:
        novos = _scrape_migalhas_pagina(pagina_url, seen)
        artigos.extend(novos)
        total_verificados = len(seen)

    if total_verificados == 0:
        print(f"  ⚠ Migalhas: nenhum link encontrado em nenhuma página.")
    print(f"  ✓ Migalhas: {len(artigos)} relevantes de {total_verificados} verificados")
    return artigos

# ---------------------------------------------------------------------------
# Gera card HTML para o site
# ---------------------------------------------------------------------------
def gerar_card(a):
    desc = f'\n        <p class="news-desc">{a["descricao"]}</p>' if a.get("descricao") else ""
    return f"""      <div class="news-card rv">
        <div class="news-src">{a["fonte"]} &mdash; {a["data"]}</div>
        <h3 class="news-title">{a["titulo"]}</h3>{desc}
        <a href="{a["link"]}" target="_blank" rel="noopener" class="news-link">Ler artigo <svg viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg></a>
      </div>"""

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("="*60)
    print(f"Marquez Advogados — Atualizador | {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("="*60)

    todos = []

    for feed in FEEDS_RSS:
        print(f"\nBuscando {feed['nome']}...")
        todos.extend(buscar_rss(feed))

    print(f"\nBuscando Migalhas (HTML)...")
    todos.extend(buscar_migalhas())

    print(f"\nTotal relevantes: {len(todos)}")

    if len(todos) < 2:
        print(f"\n⚠ Poucos artigos ({len(todos)}). Mantendo atuais.")
        return

    # Distribui igualmente entre as fontes (round-robin)
    por_fonte = {}
    for a in todos:
        por_fonte.setdefault(a["nome"], []).append(a)

    selecionados = []
    for _ in range(MAX_NOTICIAS):
        for f in FONTES_ORDEM:
            if f in por_fonte and por_fonte[f] and len(selecionados) < MAX_NOTICIAS:
                selecionados.append(por_fonte[f].pop(0))

    print(f"\n✓ {len(selecionados)} notícias selecionadas:")
    for a in selecionados:
        print(f"  [{a['nome']}] {a['titulo'][:72]}...")

    if not os.path.exists("index.html"):
        print("\n✗ index.html não encontrado!")
        return

    with open("index.html", 'r', encoding='utf-8') as f:
        html = f.read()

    cards = "\n".join(gerar_card(a) for a in selecionados)

    # Regex: captura de <div class="news-grid"> até </section>
    pattern = r'(<div class="news-grid">).*?(</div>\s*</div>\s*</section>)'
    novo, n = re.subn(pattern, f'\\1\n{cards}\n    \\2', html, flags=re.DOTALL)

    if n == 0:
        print("\n✗ Seção de notícias não encontrada no index.html.")
        return

    with open("index.html", 'w', encoding='utf-8') as f:
        f.write(novo)
    print("\n✓ index.html atualizado com sucesso!")

    os.makedirs("scripts", exist_ok=True)
    with open("scripts/ultimo_log.json", "w") as f:
        json.dump({
            "ultima_atualizacao": datetime.now(timezone.utc).isoformat(),
            "noticias": len(selecionados),
            "fontes": list(set(a["nome"] for a in selecionados))
        }, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
