#!/usr/bin/env python3
"""
Atualiza o site de animes da temporada usando a API oficial do MyAnimeList (v2).

Uso: python scripts/update.py
Requer MAL_CLIENT_ID (GitHub Secret, passado pelo workflow).
Temporada em data/config.json, por exemplo {"ano": 2026, "temporada": "fall"}.

- Lista todos os animes da temporada e gera uma página para cada um.
- Os animes do canal (data/animes.json) recebem página completa, com análise.
- Os demais recebem ficha automática, marcada para não aparecer no Google.
- Horários do Japão e de Brasília são calculados a partir do horário semanal.
- Mudanças de data só viram aviso quando há fonte oficial informada.
"""
import hashlib
import html
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"  # o GitHub Pages publica a pasta docs/
TZ_BR = ZoneInfo("America/Sao_Paulo")
TZ_JP = ZoneInfo("Asia/Tokyo")
API = "https://api.myanimelist.net/v2"
PAUSA = 1.0
USER_AGENT = "animes-temporada/1.0 (site pessoal de analises)"
CLIENT_ID = os.environ.get("MAL_CLIENT_ID", "").strip()
DESTAQUE_NOTA = 7.0  # nota mínima para ir a "Em destaque"
LIMITE_PAGINAS = 10  # trava de segurança na paginação da temporada

CAMPOS = ",".join([
    "id", "title", "alternative_titles", "synopsis", "mean", "num_episodes",
    "status", "media_type", "genres", "studios", "broadcast", "start_date", "end_date",
    "rank", "popularity", "num_list_users",
])

STATUS_LABEL = {
    "currently_airing": ("Em exibição", "Airing"),
    "finished_airing": ("Finalizado", "Finished"),
    "not_yet_aired": ("Ainda não estreou", "Not yet aired"),
}
NOME_TEMPORADA = {
    "winter": ("Inverno", "Winter"),
    "spring": ("Primavera", "Spring"),
    "summer": ("Verão", "Summer"),
    "fall": ("Outono", "Fall"),
}
DIA_INDEX = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
             "friday": 4, "saturday": 5, "sunday": 6}
DIAS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
           "sexta-feira", "sábado", "domingo"]
DIAS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ROTULOS = {
    "estudio": ("Estúdio", "Studio"),
    "generos": ("Gêneros", "Genres"),
    "episodios": ("Episódios", "Episodes"),
    "tipo": ("Tipo", "Type"),
    "inicio": ("Início da exibição", "Start date"),
    "fim": ("Fim da exibição", "End date"),
    "jp": ("Horário no Japão", "Air time in Japan"),
    "br": ("Horário no Brasil", "Air time in Brazil"),
    "proxima": ("Próxima estreia", "Next episode"),
    "nota": ("Nota no MyAnimeList", "MyAnimeList score"),
    "sinopse": ("Sinopse", "Synopsis"),
    "analise": ("Análise", "Review"),
    "ficha": ("Ficha completa no MyAnimeList", "Full page on MyAnimeList"),
    "avisos": ("Avisos", "Notices"),
    "sem_avisos": ("Nenhum aviso no momento.", "No notices at the moment."),
    "ultima": ("Última verificação", "Last check"),
    "inicio_site": ("Início", "Home"),
    "traducao": ("Tradução em português ainda não publicada.", "Portuguese translation not published yet."),
    "automatica": ("Ficha automática. A análise ainda não foi publicada.",
                   "Automatic listing. The review has not been published yet."),
    "sem_horario": ("Horário não informado", "Schedule not announced"),
    "semanal": ("Semanal", "Weekly"),
    "ranking": ("Ranking", "Rank"),
    "popularidade": ("Popularidade", "Popularity"),
    "membros": ("Membros", "Members"),
}


def bi(pt, en):
    """Texto nas duas línguas. A página mostra uma por vez, conforme o botão."""
    return f'<span class="pt">{html.escape(pt)}</span><span class="en">{html.escape(en)}</span>'


def rotulo(chave):
    pt, en = ROTULOS[chave]
    return bi(pt, en)


def ler_json(caminho, padrao):
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return padrao


def salvar_json(caminho, dados):
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def requisicao(caminho, params=None):
    url = API + caminho
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "X-MAL-CLIENT-ID": CLIENT_ID,
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    })
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                dados = json.load(resp)
            time.sleep(PAUSA)
            return dados
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                return None
            if erro.code == 403:
                print("  limite de requisições atingido, aguardando")
                time.sleep(60)
                continue
            print(f"  erro HTTP {erro.code} em {caminho}")
            return None
        except (urllib.error.URLError, TimeoutError) as erro:
            print(f"  falha de rede: {erro}")
            time.sleep(5)
    return None


def horario_semanal(broadcast):
    """Converte o horário semanal (Japão) para os horários do Japão e de Brasília."""
    if not broadcast or not broadcast.get("day_of_the_week") or not broadcast.get("start_time"):
        return None
    alvo = DIA_INDEX.get(broadcast["day_of_the_week"])
    if alvo is None:
        return None
    hoje = datetime.now(TZ_JP).date()
    data = hoje + timedelta(days=(alvo - hoje.weekday()) % 7)
    hh, mm = (int(x) for x in broadcast["start_time"].split(":")[:2])
    jp = datetime(data.year, data.month, data.day, hh, mm, tzinfo=TZ_JP)
    br = jp.astimezone(TZ_BR)
    return {
        "jp_pt": f"{DIAS_PT[jp.weekday()]} às {jp:%H:%M}",
        "jp_en": f"{DIAS_EN[jp.weekday()]} at {jp:%H:%M}",
        "br_pt": f"{DIAS_PT[br.weekday()]} às {br:%H:%M}",
        "br_en": f"{DIAS_EN[br.weekday()]} at {br:%H:%M}",
    }


def data_legivel(texto):
    if not texto:
        return "—"
    partes = texto.split("-")
    if len(partes) == 3:
        return f"{partes[2]}/{partes[1]}/{partes[0]}"
    if len(partes) == 2:
        return f"{partes[1]}/{partes[0]}"
    return partes[0]


def normalizar(dados):
    """Converte o registro da API no formato que o site usa."""
    alt = dados.get("alternative_titles") or {}
    return {
        "id": dados["id"],
        "titulo": alt.get("en") or dados.get("title") or "Sem título",
        "sinopse_en": dados.get("synopsis") or "",
        "mal_nota": dados.get("mean"),
        "episodios": dados.get("num_episodes"),
        "status": dados.get("status"),
        "tipo": (dados.get("media_type") or "").upper(),
        "estudios": [s["name"] for s in dados.get("studios", [])],
        "generos": [g["name"] for g in dados.get("genres", [])],
        "inicio": data_legivel(dados.get("start_date")),
        "fim": data_legivel(dados.get("end_date")),
        "horario": horario_semanal(dados.get("broadcast")),
        "ranking": dados.get("rank"),
        "popularidade": dados.get("popularity"),
        "membros": dados.get("num_list_users"),
        "url": f"https://myanimelist.net/anime/{dados['id']}",
    }


def listar_temporada(ano, temporada):
    """Percorre todas as páginas da temporada, da mais bem avaliada para a menos."""
    encontrados = []
    offset = 0
    for _ in range(LIMITE_PAGINAS):
        resposta = requisicao(f"/anime/season/{ano}/{temporada}", {
            "fields": CAMPOS, "limit": 100, "offset": offset, "sort": "anime_score",
        })
        if not resposta:
            break
        for item in resposta.get("data", []):
            encontrados.append(item.get("node", item))
        if not (resposta.get("paging") or {}).get("next"):
            break
        offset += 100
    return encontrados


def consultar(anime):
    """Usa o mal_id se existir; senão faz busca pelo nome e pega o primeiro resultado de TV."""
    if anime.get("mal_id"):
        dados = requisicao(f"/anime/{anime['mal_id']}", {"fields": CAMPOS})
        return normalizar(dados) if dados else None
    resposta = requisicao("/anime", {"q": anime["busca"], "limit": 5, "fields": "id,title,media_type"})
    for item in (resposta or {}).get("data", []):
        no = item.get("node", item)
        if no.get("media_type") == "tv":
            return consultar({"mal_id": no["id"]})
    return None


def proxima_estreia(anime):
    """Retorna (episódio, timestamp) da próxima estreia, ou None se não houver data conhecida."""
    manual = (anime or {}).get("proxima_estreia") or {}
    if manual.get("data"):
        ts = datetime.fromisoformat(manual["data"]).timestamp()
        return manual.get("episodio"), ts
    return None


def formatar_data(ts):
    if not ts:
        return "sem data confirmada"
    return datetime.fromtimestamp(ts, TZ_BR).strftime("%d/%m/%Y às %H:%M")


def assinatura(media, anime):
    conteudo = {
        "media": media,
        "editorial": {k: anime.get(k) for k in ("analise", "nota", "proxima_estreia", "sinopse_pt")},
    }
    bruto = json.dumps(conteudo, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


CSS = """
:root { --bg:#0f1115; --card:#181b22; --texto:#eceef3; --muted:#9aa3b2; --acento:#7c5cff; --verde:#2ecc71; --azul:#3498db; --cinza:#6b7385; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--texto); font-family: system-ui, -apple-system, "Segoe UI", sans-serif; line-height:1.6; }
a { color:var(--acento); }
.topo { background: linear-gradient(135deg, #2b1d5c 0%, #0f1115 75%); padding:36px 20px; text-align:center; border-bottom:1px solid #22262f; }
.topo h1 { margin:0; font-size:2rem; }
.topo p { margin:6px 0 0; color:var(--muted); }
.barra { max-width:1080px; margin:0 auto; padding:14px 20px 0; display:flex; justify-content:space-between; align-items:center; gap:12px; }
.barra a { font-weight:600; text-decoration:none; }
.idioma { background:#252a35; color:var(--texto); border:1px solid #333a48; border-radius:8px; padding:6px 12px; cursor:pointer; font-weight:600; }
.wrap { max-width:1080px; margin:0 auto; padding:0 20px 48px; }
h1 { font-size:1.8rem; margin:24px 0 8px; }
h2 { font-size:1.25rem; margin:32px 0 14px; border-left:4px solid var(--acento); padding-left:10px; }
.avisos { background:#2a2310; border:1px solid #5a4a16; border-radius:10px; padding:10px 18px; }
.avisos ul { margin:6px 0; padding-left:18px; }
.grade { display:grid; grid-template-columns:repeat(auto-fill, minmax(240px, 1fr)); gap:16px; }
.card { background:var(--card); border-radius:12px; padding:18px; border-top:4px solid var(--cinza); text-decoration:none; color:inherit; transition:transform .15s; }
.card:hover { transform:translateY(-3px); }
.card.exibicao { border-top-color:var(--verde); }
.card.finalizado { border-top-color:var(--azul); }
.card h3 { margin:0 0 10px; font-size:1.05rem; }
.selo { display:inline-block; font-size:.75rem; padding:2px 10px; border-radius:99px; background:#252a35; color:var(--muted); }
.linha { color:var(--muted); font-size:.9rem; margin:8px 0 0; }
.ficha { display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:10px; background:var(--card); border-radius:12px; padding:16px 18px; list-style:none; margin:16px 0; }
.ficha li { color:var(--muted); }
.ficha strong { color:var(--texto); display:block; }
.bloco { background:var(--card); border-radius:12px; padding:18px; }
.rodape { color:var(--cinza); font-size:.85em; margin-top:32px; }
.en { display:none; }
body.en .en { display:revert; }
body.en .pt { display:none; }
"""


def casca(titulo_pagina, corpo, base="", noindex=False):
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{robots}
<title>{html.escape(titulo_pagina)}</title>
<style>{CSS}</style>
</head>
<body>
<header class="topo">
<h1>Animes da Temporada</h1>
<p>{bi("Acompanhamento, fichas e análises", "Tracking, listings and reviews")}</p>
</header>
<div class="barra">
<a href="{base}index.html">{rotulo("inicio_site")}</a>
<button class="idioma" onclick="document.body.classList.toggle('en')">PT / EN</button>
</div>
<main class="wrap">
{corpo}
</main>
</body>
</html>
"""


def pagina_anime(media, anime, agora):
    curado = anime is not None
    anime = anime or {}
    nome = media["titulo"]
    estudios = ", ".join(media["estudios"]) or "—"
    generos = ", ".join(media["generos"]) or "—"
    prox = proxima_estreia(anime)
    if prox:
        ep, ts = prox
        proximo = f"Episódio {ep}: {formatar_data(ts)}" if ep else formatar_data(ts)
    else:
        proximo = "—"
    st_pt, st_en = STATUS_LABEL.get(media["status"], ("—", "—"))
    if media["horario"]:
        h = media["horario"]
        horario_jp = bi(h["jp_pt"], h["jp_en"])
        horario_br = bi(h["br_pt"], h["br_en"])
    else:
        horario_jp = horario_br = bi("Não informado", "Not announced")
    sinopse_pt = anime.get("sinopse_pt")
    if sinopse_pt:
        bloco_sinopse = f'<p class="pt">{html.escape(sinopse_pt)}</p>'
        aviso_traducao = ""
    else:
        bloco_sinopse = f'<p class="pt">{html.escape(media["sinopse_en"] or "—")}</p>'
        aviso_traducao = f'<p class="rodape">{rotulo("traducao")}</p>'
    sinopse_en = f'<p class="en">{html.escape(media["sinopse_en"] or "—")}</p>'
    if curado:
        paragrafos = "".join(f"<p>{html.escape(p)}</p>" for p in (anime.get("analise") or "").split("\n\n") if p.strip())
        if not paragrafos:
            paragrafos = f"<p><em>{bi('Análise em breve.', 'Review coming soon.')}</em></p>"
        nota = anime.get("nota")
        bloco_nota = f"<p><strong>{bi('Sua nota', 'Your score')}:</strong> {nota}/10</p>" if nota is not None else ""
        bloco_analise = f'<h2>{rotulo("analise")}</h2><div class="bloco">{bloco_nota}{paragrafos}</div>'
    else:
        bloco_analise = f'<p class="linha">{rotulo("automatica")}</p>'
    corpo = f"""<h1>{html.escape(nome)}</h1>
<p><span class="selo">{bi(st_pt, st_en)}</span></p>
<ul class="ficha">
<li>{rotulo("tipo")}{html.escape(media['tipo'] or '—')}</li>
<li>{rotulo("estudio")}{html.escape(estudios)}</li>
<li>{rotulo("generos")}{html.escape(generos)}</li>
<li>{rotulo("episodios")}{html.escape(str(media['episodios'] or '—'))}</li>
<li>{rotulo("inicio")}{html.escape(media['inicio'])}</li>
<li>{rotulo("fim")}{html.escape(media['fim'])}</li>
<li>{rotulo("jp")}{horario_jp}</li>
<li>{rotulo("br")}{horario_br}</li>
<li>{rotulo("proxima")}{html.escape(proximo)}</li>
<li>{rotulo("nota")}{html.escape(str(media['mal_nota'] or '—'))}</li>
<li>{rotulo("ranking")}#{html.escape(str(media['ranking'] or '—'))}</li>
<li>{rotulo("popularidade")}#{html.escape(str(media['popularidade'] or '—'))}</li>
<li>{rotulo("membros")}{html.escape(f"{media['membros']:,}".replace(",", ".") if media['membros'] else '—')}</li>
</ul>
<h2>{rotulo("sinopse")}</h2>
<div class="bloco">{bloco_sinopse}{sinopse_en}{aviso_traducao}</div>
{bloco_analise}
<p><a href="{html.escape(media['url'])}">{rotulo("ficha")}</a></p>
<p class="rodape">{rotulo("ultima")}: {html.escape(agora)}</p>"""
    return casca(nome, corpo, base="../", noindex=not curado)


ORDEM_TEMPORADAS = ["winter", "spring", "summer", "fall"]


def lista_temporadas(config):
    """Temporada atual primeiro, depois todas as quatro de cada ano extra, sem repetir."""
    lista = [dict(config["temporada_atual"])]
    for ano in config.get("anos_extras", []):
        for t in ORDEM_TEMPORADAS:
            lista.append({"ano": ano, "temporada": t})
    vistos, unicas = set(), []
    for s in lista:
        chave = (s["ano"], s["temporada"])
        if chave not in vistos:
            vistos.add(chave)
            unicas.append(s)
    return unicas


def arquivo_temporada(s):
    return f"{s['temporada']}-{s['ano']}"


def nome_temporada(s):
    pt, en = NOME_TEMPORADA.get(s["temporada"], ("", ""))
    return bi(f"{pt} {s['ano']}", f"{en} {s['ano']}")


def classe_status(status):
    return {"currently_airing": "exibicao", "finished_airing": "finalizado"}.get(status, "")


def cartao(c, prefixo=""):
    st_pt, st_en = STATUS_LABEL.get(c.get("status"), ("—", "—"))
    if c.get("status") == "finished_airing":
        periodo = bi(f"{c.get('inicio', '—')} a {c.get('fim', '—')}", f"{c.get('inicio', '—')} to {c.get('fim', '—')}")
    elif c.get("horario"):
        h = c["horario"]
        periodo = bi(f"Brasil: {h['br_pt']}", f"Brazil: {h['br_en']}")
    else:
        periodo = rotulo("sem_horario")
    ranking = c.get("ranking")
    return (
        f'<a class="card {classe_status(c.get("status"))}" href="{prefixo}anime/{html.escape(c["slug"])}.html">'
        f'<h3>{html.escape(c["nome"])}</h3>'
        f'<span class="selo">{bi(st_pt, st_en)}</span>'
        f'<p class="linha">{html.escape(c.get("tipo") or "")} · {html.escape(str(c.get("episodios") or "—"))} ep.'
        f'{" · #" + str(ranking) if ranking else ""}</p>'
        f'<p class="linha">{periodo}</p></a>'
    )


def secao_cards(titulo, lista, prefixo=""):
    if not lista:
        return ""
    return f'<h2>{bi(*titulo)}</h2><div class="grade">' + "".join(cartao(c, prefixo) for c in lista) + "</div>"


def pagina_inicial(grupos, avisos, agora, atual, temps_info):
    if avisos:
        itens_avisos = "".join(
            f"<li><strong>{html.escape(a['texto'])}</strong> "
            f"<small>({html.escape(a['data_registro'])})</small></li>"
            for a in avisos
        )
    else:
        itens_avisos = f"<li>{rotulo('sem_avisos')}</li>"
    secoes = "".join(secao_cards(titulo, lista) for titulo, lista in grupos)
    if not secoes:
        secoes = f'<p class="linha">{bi("A lista desta temporada ainda não está disponível.", "The list for this season is not available yet.")}</p>'
    corpo = f"""<h1>{nome_temporada(atual)}</h1>
<p class="linha"><a href="temporadas/index.html">{bi("Ver todas as temporadas", "See all seasons")}</a></p>
<h2>{rotulo("avisos")}</h2>
<section class="avisos"><ul>{itens_avisos}</ul></section>
{secoes}
<p class="rodape">{rotulo("ultima")}: {html.escape(agora)}</p>"""
    return casca("Animes da temporada", corpo, base="")


def pagina_temporada(s, cards, agora):
    if cards:
        conteudo = f'<div class="grade">' + "".join(cartao(c, "../") for c in cards) + "</div>"
    else:
        conteudo = f'<p class="linha">{bi("A lista desta temporada ainda não está disponível no MyAnimeList.", "The list for this season is not available on MyAnimeList yet.")}</p>'
    aviso = f'<p class="linha">{bi("A lista pode mudar até o fim da temporada.", "The list may change until the end of the season.")}</p>'
    corpo = f"""<h1>{nome_temporada(s)}</h1>
{aviso}
{conteudo}
<p class="rodape">{rotulo("ultima")}: {html.escape(agora)}</p>"""
    return casca(f"{s['temporada']} {s['ano']}", corpo, base="../")


def pagina_indice_temporadas(indice, agora):
    itens = "".join(
        f'<li><a href="{arquivo_temporada(s)}.html">{nome_temporada(s)}</a> '
        f'<span class="linha">({qtd} {bi("animes", "animes")})</span></li>'
        for s, qtd in indice
    )
    corpo = f"""<h1>{bi("Todas as temporadas", "All seasons")}</h1>
<ul class="ficha">{itens}</ul>
<p class="rodape">{rotulo("ultima")}: {html.escape(agora)}</p>"""
    return casca("Temporadas", corpo, base="../")


def ordenar_por_nota(lista):
    return sorted(lista, key=lambda c: c.get("mal_nota") or 0, reverse=True)


def carregar_animes():
    """Lê data/animes.json aceitando lista ou dicionário, e avisa de blocos inválidos."""
    bruto = ler_json(DATA / "animes.json", [])
    if isinstance(bruto, dict):
        bruto = [dict(v, slug=v.get("slug", k)) for k, v in bruto.items() if isinstance(v, dict)]
    if not isinstance(bruto, list):
        print("ERRO: data/animes.json precisa ser uma lista de animes, entre colchetes [ ].")
        sys.exit(1)
    validos = []
    for item in bruto:
        if isinstance(item, dict) and item.get("slug") and (item.get("mal_id") or item.get("busca")):
            validos.append(item)
        else:
            print(f"AVISO: bloco ignorado em animes.json (precisa de 'slug' e de 'mal_id' ou 'busca'): {str(item)[:80]}")
    return validos


def main():
    if not CLIENT_ID:
        print("ERRO: MAL_CLIENT_ID não definido. Confira o Secret no GitHub e o campo env do workflow.")
        sys.exit(1)

    config = ler_json(DATA / "config.json", {
        "temporada_atual": {"ano": 2026, "temporada": "fall"},
        "anos_extras": [2027],
    })
    temporadas = lista_temporadas(config)
    print("Fonte: API oficial do MyAnimeList (v2)")
    for s in temporadas:
        print(f"  temporada: {s['temporada']} {s['ano']}")

    animes = carregar_animes()
    estado = ler_json(DATA / "estado.json", {})
    pendentes = ler_json(DATA / "pendentes.json", [])
    avisos = ler_json(DATA / "avisos.json", [])
    agora = datetime.now(TZ_BR).strftime("%d/%m/%Y %H:%M")
    (DOCS / "anime").mkdir(parents=True, exist_ok=True)
    (DOCS / "temporadas").mkdir(parents=True, exist_ok=True)

    colecao, membros = {}, {}
    for s in temporadas:
        brutos = listar_temporada(s["ano"], s["temporada"])
        ids = []
        for bruto in brutos:
            n = normalizar(bruto)
            colecao[n["id"]] = n
            ids.append(n["id"])
        membros[arquivo_temporada(s)] = ids
        print(f"  {s['temporada']} {s['ano']}: {len(ids)} animes")

    curados = {}
    for anime in animes:
        print(f"Verificando {anime['slug']}...")
        media = consultar(anime)
        if media is None:
            print("  não encontrado ou erro; mantendo os dados anteriores")
            continue
        colecao[media["id"]] = media
        curados[media["id"]] = anime

    atualizadas = 0
    slug_por_id = {}
    for mid, media in colecao.items():
        anime = curados.get(mid)
        slug = anime["slug"] if anime else f"mal-{mid}"
        slug_por_id[mid] = slug
        antigo = estado.get(slug, {})
        ep_novo, at_novo = proxima_estreia(anime) or (None, None)

        if anime and ep_novo and antigo.get("ep") == ep_novo and antigo.get("airingAt") and at_novo and antigo["airingAt"] != at_novo:
            aviso = {
                "anime": media["titulo"], "episodio": ep_novo,
                "de": formatar_data(antigo["airingAt"]), "para": formatar_data(at_novo),
                "data_registro": agora,
            }
            if anime.get("fonte_oficial"):
                aviso["fonte"] = anime["fonte_oficial"]
                aviso["texto"] = (f"A estreia do episódio {ep_novo} de {aviso['anime']} mudou de "
                                  f"{aviso['de']} para {aviso['para']}, segundo a fonte oficial.")
                avisos.insert(0, aviso)
                print("  mudança de data publicada como aviso na capa")
            else:
                pendentes.append(aviso)
                print("  mudança de data enviada para revisão (sem fonte oficial)")

        assin = assinatura(media, anime or {})
        pagina = DOCS / "anime" / f"{slug}.html"
        if antigo.get("hash") != assin or not pagina.exists():
            pagina.write_text(pagina_anime(media, anime, agora), encoding="utf-8")
            atualizadas += 1

        resumo = None
        if at_novo:
            resumo = f"Episódio {ep_novo}: {formatar_data(at_novo)}" if ep_novo else formatar_data(at_novo)
        estado[slug] = {
            "slug": slug, "nome": media["titulo"], "curado": anime is not None,
            "hash": assin, "status": media["status"], "tipo": media["tipo"],
            "episodios": media["episodios"], "mal_nota": media["mal_nota"],
            "ranking": media["ranking"], "popularidade": media["popularidade"],
            "membros": media["membros"], "inicio": media["inicio"], "fim": media["fim"],
            "horario": media["horario"], "ep": ep_novo, "airingAt": at_novo,
            "proximo": resumo, "verificado": agora,
        }

    print(f"  páginas de anime atualizadas nesta execução: {atualizadas}")

    def cards_de(ids):
        return [estado[slug_por_id[i]] for i in ids if i in slug_por_id and slug_por_id[i] in estado]

    atual = temporadas[0]
    cards_atual = cards_de(membros[arquivo_temporada(atual)])
    slugs_atuais_set = set(slug_por_id.values())
    canal = ordenar_por_nota([c for c in estado.values() if c.get("curado") and c.get("slug") in slugs_atuais_set])
    outros = ordenar_por_nota([c for c in cards_atual if not c.get("curado")])
    destaque = [c for c in outros if (c.get("mal_nota") or 0) >= DESTAQUE_NOTA]
    resto = [c for c in outros if (c.get("mal_nota") or 0) < DESTAQUE_NOTA]
    grupos = [
        ((("Acompanhando no canal", "Following on the channel")), canal),
        ((("Em destaque", "Highlights")), destaque),
        ((("Outros da temporada", "Rest of the season")), resto),
    ]

    indice = []
    for s in temporadas:
        cards = ordenar_por_nota(cards_de(membros[arquivo_temporada(s)]))
        (DOCS / "temporadas" / f"{arquivo_temporada(s)}.html").write_text(
            pagina_temporada(s, cards, agora), encoding="utf-8")
        indice.append((s, len(cards)))
    (DOCS / "temporadas" / "index.html").write_text(pagina_indice_temporadas(indice, agora), encoding="utf-8")

    salvar_json(DATA / "estado.json", estado)
    salvar_json(DATA / "pendentes.json", pendentes)
    salvar_json(DATA / "avisos.json", avisos[:50])
    (DOCS / "index.html").write_text(pagina_inicial(grupos, avisos[:10], agora, atual, indice), encoding="utf-8")
    print(f"Concluído. Itens aguardando revisão: {len(pendentes)}")


if __name__ == "__main__":
    main()
