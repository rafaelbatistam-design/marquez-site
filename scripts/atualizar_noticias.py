#!/usr/bin/env python3
"""
Marquez Advogados — Atualizador automático de notícias
Fontes: STJ Informativo, STJ Notícias, Conjur, Migalhas, Jota, TJSP
Roda toda terça-feira às 20h (horário de Brasília = 23h UTC)
"""

import urllib.request
import xml.etree.ElementTree as ET
import re, os, json
from datetime import datetime, timezone
from html import unescape

FEEDS_RSS = [
    {"nome":"STJ_INFO",    "url":"https://processo.stj.jus.br/jurisprudencia/externo/InformativoFeed","label":"STJ — Informativo","priority":1},
    {"nome":"Conjur",      "url":"https://www.conjur.com.br/feed/",                                    "label":"Conjur",           "priority":2},
    {"nome":"Migalhas",    "url":"https://www.migalhas.com.br/rss/quentes",                            "label":"Migalhas",         "priority":2},
    {"nome":"Jota",        "url":"https://www.jota.info/feed",                                         "label":"Jota",             "priority":2},
]

PAGINAS_HTML = [
    {"nome":"STJ_NOTICIAS","url":"https://www.stj.jus.br/sites/portalp/Comunicacao/Ultimas-noticias","label":"STJ — Notícias","priority":1},
    {"nome":"TJSP",        "url":"https://www.tjsp.jus.br/SecaoDireitoPrivado/Gapri/BoletinsJulgadosSelecionados","label":"TJSP — Boletim","priority":2},
]

KEYWORDS = [
    "societario","socio","dissolucao","haveres","joint venture","fusao","aquisicao",
    "m&a","reestruturacao","due diligence","governanca","contrato","clausula",
    "inadimplemento","rescisao","take or pay","mutuo","fornecimento","distribuicao",
    "imobiliario","imovel","distrato","incorporacao","alienacao fiduciaria","locacao",
    "leilao","sucessao","inventario","heranca","holding","testamento","partilha",
    "stj","stf","tjsp","tribunal","recurso especial","agencia reguladora",
    "arbitragem","mediacao","litigio","acordao","julgamento","turma",
    "incentivo fiscal","terceiro setor","empresarial","codigo civil","lgpd",
    "compliance","anticorrupcao","regulatorio","direito privado",
]

MAX_NOTICIAS = 6
MESES_PT = {"Jan":"Jan","Feb":"Fev","Mar":"Mar","Apr":"Abr","May":"Mai","Jun":"Jun",
            "Jul":"Jul","Aug":"Ago","Sep":"Set","Oct":"Out","Nov":"Nov","Dec":"Dez"}
HEADERS = {"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0 Safari/537.36",
           "Accept":"text/html,application/xml,*/*","Accept-Language":"pt-BR,pt;q=0.9"}

def normalizar(t):
    return t.lower().translate(str.maketrans('ãçéêóúáíàâôõü','aceeoualaaonu'))

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

def e_relevante(titulo, desc="", nome=""):
    if nome in ("STJ_INFO","STJ_NOTICIAS","TJSP"): return True
    txt = normalizar(titulo+" "+desc)
    return any(normalizar(k) in txt for k in KEYWORDS)

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r: return r.read()

def buscar_rss(feed):
    artigos = []
    try:
        root = ET.fromstring(fetch(feed["url"]))
        ns = {'a':'http://www.w3.org/2005/Atom'}
        items = root.findall('.//item') or root.findall('.//a:entry',ns)
        for it in items[:25]:
            def g(tag,at=None):
                el = it.find(tag)
                if el is None and at: el = it.find(at,ns)
                return (el.text or "").strip() if el is not None else ""
            titulo = limpar(g('title','a:title'))
            link = g('link','a:link') or (it.find('a:link',ns) or type('x',(),({"get":lambda s,k,d="":d})())).get('href','')
            desc = limpar(g('description') or g('summary','a:summary'))
            data = formatar_data(g('pubDate') or g('published','a:published') or g('updated','a:updated'))
            if titulo and link and e_relevante(titulo,desc,feed["nome"]):
                artigos.append({"titulo":titulo,"link":link,"descricao":truncar(desc),
                                "data":data,"fonte":feed["label"],"nome":feed["nome"],"priority":feed["priority"]})
        print(f"  ✓ {feed['nome']} (RSS): {len(artigos)}")
    except Exception as e:
        print(f"  ✗ {feed['nome']} (RSS): {e}")
    return artigos

def buscar_html(pagina):
    artigos = []
    try:
        html = fetch(pagina["url"]).decode('utf-8','ignore')
        links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]{15,200})</a>',html,re.I)
        base = re.match(r'(https?://[^/]+)',pagina["url"])
        base_url = base.group(1) if base else ""
        data_str = f"{MESES_PT.get(datetime.now().strftime('%b'),'')} {datetime.now().year}"
        vistos, unicos = set(), []
        for href,txt in links[:60]:
            titulo = limpar(txt)
            if len(titulo)<15: continue
            link = href if href.startswith('http') else (base_url+href if href.startswith('/') else None)
            if not link: continue
            if e_relevante(titulo,"",pagina["nome"]):
                t = normalizar(titulo)
                if t not in vistos:
                    vistos.add(t)
                    unicos.append({"titulo":titulo,"link":link,"descricao":"",
                                   "data":data_str,"fonte":pagina["label"],"nome":pagina["nome"],"priority":pagina["priority"]})
        print(f"  ✓ {pagina['nome']} (HTML): {len(unicos[:5])}")
        artigos = unicos[:5]
    except Exception as e:
        print(f"  ✗ {pagina['nome']} (HTML): {e}")
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
    for pag in PAGINAS_HTML:
        print(f"\nBuscando {pag['nome']}...")
        todos.extend(buscar_html(pag))

    if len(todos) < 3:
        print(f"\n⚠ Poucos artigos ({len(todos)}). Mantendo atuais.")
        return

    # Selecionar: prioridade alta primeiro, depois distribuir por fonte
    alta = [a for a in todos if a["priority"]==1]
    normal = [a for a in todos if a["priority"]==2]

    selecionados = []
    # Até 2 de alta prioridade
    for a in alta:
        if len(selecionados)<2: selecionados.append(a)

    # Completar com fontes normais
    por_fonte = {}
    for a in normal: por_fonte.setdefault(a["nome"],[]).append(a)
    for _ in range(2):
        for f in ["Conjur","Migalhas","Jota"]:
            if f in por_fonte and por_fonte[f] and len(selecionados)<MAX_NOTICIAS:
                selecionados.append(por_fonte[f].pop(0))

    restantes = [a for arts in por_fonte.values() for a in arts]
    while len(selecionados)<MAX_NOTICIAS and restantes:
        selecionados.append(restantes.pop(0))

    print(f"\n✓ {len(selecionados)} notícias selecionadas:")
    for a in selecionados: print(f"  [{a['nome']}] {a['titulo'][:72]}...")

    if not os.path.exists("index.html"):
        print("\n✗ index.html não encontrado!")
        return

    with open("index.html",'r',encoding='utf-8') as f: html = f.read()

    cards = "\n".join(gerar_card(a) for a in selecionados)
    pattern = r'(<div class="news-grid">)\s*.*?\s*(</div>\s*</div>\s*</section>\s*<div class="nl-bar)'
    novo, n = re.subn(pattern, f'\\1\n{cards}\n    \\2', html, flags=re.DOTALL)

    if n==0:
        print("\n✗ Seção de notícias não encontrada.")
        return

    with open("index.html",'w',encoding='utf-8') as f: f.write(novo)
    print("\n✓ index.html atualizado!")

    os.makedirs("scripts",exist_ok=True)
    with open("scripts/ultimo_log.json","w") as f:
        json.dump({"ultima_atualizacao":datetime.now(timezone.utc).isoformat(),
                   "noticias":len(selecionados),
                   "fontes":list(set(a["nome"] for a in selecionados))},f,indent=2,ensure_ascii=False)

if __name__=="__main__":
    main()
