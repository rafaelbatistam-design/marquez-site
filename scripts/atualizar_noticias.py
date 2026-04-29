#!/usr/bin/env python3
"""
Marquez Advogados — Atualizador automático de notícias
Fontes: Conjur, Jota
Roda toda terça-feira às 20h (horário de Brasília = 23h UTC)
"""

import urllib.request
import xml.etree.ElementTree as ET
import re, os, json
from datetime import datetime, timezone
from html import unescape

FEEDS_RSS = [
    {"nome":"Conjur", "url":"https://www.conjur.com.br/feed/",  "label":"Conjur", "priority":1},
    {"nome":"Jota",   "url":"https://www.jota.info/feed",       "label":"Jota",   "priority":1},
]

# ---------------------------------------------------------------------------
# Keywords extraídas diretamente das áreas de atuação do escritório
# ---------------------------------------------------------------------------

KEYWORDS = [
    # --- CONTRATOS ---
    "contrato","contratos","contratual","contratualmente",
    "contrato comercial","contrato empresarial","contrato de compra e venda",
    "contrato de locacao","contrato de prestacao de servicos",
    "contrato de distribuicao","contrato de fornecimento",
    "opcao de compra","stock option","contrato de investimento",
    "mutuo conversivel","take or pay","joint venture","joint ventures",
    "consorcio","consorcios","parceria empresarial","parcerias empresariais",
    "inadimplemento contratual","rescisao contratual","revisao contratual",
    "quebra contratual","inexecucao contratual","penalidade contratual",
    "clausula contratual","distrato","negociacao contratual",
    "elaboracao de contrato","redacao de contrato",

    # --- IMOBILIARIO E CONSTRUCAO ---
    "imovel","imobiliario","imobiliaria","locacao","locatario","locador",
    "aquisicao de imovel","imovel urbano","imovel rural",
    "incorporacao imobiliaria","incorporadora","incorporacao",
    "built to suit","construcao civil","construcao","construtora",
    "dispute board","dispute boards","alienacao fiduciaria",
    "leilao judicial","leilao extrajudicial","distrato imobiliario",
    "contrato de locacao","despejo","retomada de imovel",
    "due diligence imobiliaria","regularizacao fundiaria",
    "condominio","compra e venda de imovel","registro de imovel",

    # --- PRE-LITIGIO E RESOLUCAO DE DISPUTAS ---
    "pre-litigio","pre litigio","resolucao de disputas","resolucao de conflitos",
    "mediacao","mediador","camara de mediacao","conciliacao","conciliador",
    "arbitragem","arbitro","camara de arbitragem","tribunal arbitral",
    "clausula compromissoria","compromisso arbitral","sentenca arbitral",
    "negociacao","acordo extrajudicial","prevencao de litigio",
    "avaliacao de risco","gestao de conflito",

    # --- FAMILIA, SUCESSOES E INVENTARIOS ---
    "inventario","heranca","espolio","partilha","testamento",
    "planejamento sucessorio","planejamento patrimonial","sucessao",
    "holding familiar","holding patrimonial","doacao","meacao",
    "divorcio","separacao","uniao estavel","regime de bens",
    "direito de familia","curatela","tutela","guarda",
    "disputa familiar","litigio familiar","conflito familiar",
    "transmissao de patrimonio","succession",

    # --- DISPUTAS SOCIETARIAS ---
    "disputa societaria","litigio societario","contencioso societario",
    "apuracao de haveres","dissolucao de sociedade","dissolucao parcial",
    "exclusao de socio","retirada de socio","direito de retirada",
    "acordo de socios","conflito entre socios","briga de socios",
    "desconsideracao da personalidade juridica","responsabilidade do socio",
    "societario","direito societario","governanca corporativa",
    "reestruturacao societaria","reorganizacao societaria",
    "aquisicao de participacao","alienacao de participacao",
    "due diligence","m&a","fusao","aquisicao","cisao","incorporacao societaria",

    # --- DISPUTAS CONTRATUAIS ---
    "disputa contratual","litigio contratual","conflito contratual",
    "inadimplemento","inadimplente","mora","execucao contratual",

    # --- DISPUTAS IMOBILIARIAS ---
    "disputa imobiliaria","litigio imobiliario","conflito imobiliario",
    "despejo","reintegracao de posse","acao possessoria","usucapiao",

    # --- RESPONSABILIDADE CIVIL ---
    "responsabilidade civil","dano","indenizacao","reparacao de danos",
    "responsabilidade contratual","responsabilidade extracontratual",
    "ato ilicito","nexo causal","dano moral","dano material","dano emergente",
    "lucro cessante","perda de chance",

    # --- QUESTOES REGULATORIAS ---
    "regulatorio","regulatoria","agencia reguladora","anatel","aneel",
    "anp","anvisa","antaq","antf","cvm","bacen","banco central",
    "compliance","licenciamento","autorizacao regulatoria",
    "infração regulatoria","processo administrativo","auto de infracao",
]

# ---------------------------------------------------------------------------

MAX_NOTICIAS = 6
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

def truncar(t,n=165):
    return t if len(t)<=n else t[:n].rsplit(' ',1)[0].rstrip('.,;:')+'\u2026'

def e_relevante(titulo, desc=""):
    txt = normalizar(titulo + " " + desc)
    matched = [k for k in KEYWORDS if normalizar(k) in txt]
    if matched:
        print(f"    → match: {matched[:3]}")
    return len(matched) > 0

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r: return r.read()

def buscar_rss(feed):
    artigos = []
    try:
        root = ET.fromstring(fetch(feed["url"]))
        ns = {'a':'http://www.w3.org/2005/Atom'}
        items = root.findall('.//item') or root.findall('.//a:entry',ns)
        for it in items[:30]:
            def g(tag,at=None):
                el = it.find(tag)
                if el is None and at: el = it.find(at,ns)
                return (el.text or "").strip() if el is not None else ""
            titulo = limpar(g('title','a:title'))
            link = g('link','a:link') or (it.find('a:link',ns) or type('x',(),({"get":lambda s,k,d="":d})())).get('href','')
            desc = limpar(g('description') or g('summary','a:summary'))
            data = formatar_data(g('pubDate') or g('published','a:published') or g('updated','a:updated'))
            if titulo and link:
                print(f"  Checando: {titulo[:60]}...")
                if e_relevante(titulo, desc):
                    artigos.append({"titulo":titulo,"link":link,"descricao":truncar(desc),
                                    "data":data,"fonte":feed["label"],"nome":feed["nome"],"priority":feed["priority"]})
        print(f"  ✓ {feed['nome']}: {len(artigos)} relevantes de {len(items)} verificados")
    except Exception as e:
        print(f"  ✗ {feed['nome']}: {e}")
    return artigos

def gerar_card(a):
    desc = f'\n        <p class="news-desc">{a["descricao"]}</p>' if a["descricao"] else ""
    return f"""      <div class="news-card rv">
        <div class="news-src">{a["fonte"]} &mdash; {a["data"]}</div>
        <h3 class="news-title">{a["titulo"]}</h3>{desc}
        <a href="{a["link"]}" target="_blank" rel="noopener" class="news-link">Ler artigo <svg viewBox="0 0 24 24" fill="none" stroke-width="1.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg></a>
      </div>"""

def main():
    print("="*60)
    print(f"Marquez Advogados — Atualizador | {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("="*60)

    todos = []
    for feed in FEEDS_RSS:
        print(f"\nBuscando {feed['nome']}...")
        todos.extend(buscar_rss(feed))

    print(f"\nTotal relevantes: {len(todos)}")

    if len(todos) < 2:
        print(f"\n⚠ Poucos artigos ({len(todos)}). Mantendo atuais.")
        return

    # Distribuir igualmente entre as fontes
    por_fonte = {}
    for a in todos:
        por_fonte.setdefault(a["nome"], []).append(a)

    selecionados = []
    for _ in range(MAX_NOTICIAS):
        for f in ["Conjur", "Jota"]:
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
    pattern = r'(<div class="news-grid">)\s*.*?\s*(</div>\s*</div>\s*</section>\s*<div class="nl-bar)'
    novo, n = re.subn(pattern, f'\\1\n{cards}\n    \\2', html, flags=re.DOTALL)

    if n == 0:
        print("\n✗ Seção de notícias não encontrada.")
        return

    with open("index.html", 'w', encoding='utf-8') as f:
        f.write(novo)
    print("\n✓ index.html atualizado!")

    os.makedirs("scripts", exist_ok=True)
    with open("scripts/ultimo_log.json", "w") as f:
        json.dump({"ultima_atualizacao": datetime.now(timezone.utc).isoformat(),
                   "noticias": len(selecionados),
                   "fontes": list(set(a["nome"] for a in selecionados))},
                  f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
