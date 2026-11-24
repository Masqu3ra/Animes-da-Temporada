#!/usr/bin/env python3
"""
Atualiza o site de animes da temporada usando a API pública do Jikan (MyAnimeList).

Uso: python scripts/update.py

- Lê data/animes.json (animes acompanhados, IDs do MyAnimeList e textos editoriais).
- Consulta o Jikan para cada anime (sem chave de API).
- Regenera a página só dos animes cujos dados mudaram.
- Avisos de mudança de data:
    * a data da próxima estreia vem de "proxima_estreia" no animes.json (você preenche
      a partir do anúncio oficial) ou de uma fonte automática, quando houver.
    * se a data mudar para o mesmo episódio e o anime tiver "fonte_oficial",
      o aviso vai para a capa do site.
    * sem "fonte_oficial", a mudança vai para data/pendentes.json para revisão.
"""
import hashlib
import html
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"  # o GitHub Pages publica a pasta docs/
TZ = ZoneInfo("America/Sao_Paulo")
API = "https://api.jikan.moe/v4"
PAUSA = 1.5  # o Jikan aceita cerca de 3 requisições por segundo e 60 por minuto
USER_AGENT = "animes-temporada/1.0 (site pessoal de análises)"

STATUS = {
    "Currently Airing": "Em exibição",
    "Finished Airing": "Finalizado",
    "Not yet aired": "Ainda não estreou",
}


def ler_json(caminho, padrao):
    if caminho.exists():
        return json.loads(caminho.read_text(encoding="utf-8"))
    return padrao


def salvar_json(caminho, dados):
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


def requisicao(caminho):
    req = urllib.request.Request(
        API + caminho,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                dados = json.load(resp)
            time.sleep(PAUSA)
            return dados
        except urllib.error.HTTPError as erro:
            if erro.code == 429:  # limite atingido: espera e tenta de novo
                time.sleep(60)
                continue
            print(f"  erro HTTP {erro.code}")
            return None
        except (urllib.error.URLError, TimeoutError) as erro:
            print(f"  falha de rede: {erro}")
            time.sleep(5)
    return None


def consultar(anime):
    """Usa o mal_id se existir; senão faz busca pelo nome e pega o primeiro resultado de TV."""
    if anime.get("mal_id"):
        resposta = requisicao(f"/anime/{anime['mal_id']}")
        return (resposta or {}).get("data")
    busca = urllib.parse.quote(anime["busca"])
    resposta = requisicao(f"/anime?q={busca}&type=tv&limit=1")
    lista = (resposta or {}).get("data") or []
    return lista[0] if lista else None


def proxima_estreia(anime):
    """Retorna (episódio, timestamp) da próxima estreia, ou None se não houver data conhecida.

    Prioridade: data preenchida à mão em animes.json.
    Ponto de extensão: quando houver uma fonte automática confiável de datas,
    ela entra aqui, retornando a mesma tupla.
    """
    manual = anime.get("proxima_estreia") or {}
    if manual.get("data"):
        ts = datetime.fromisoformat(manual["data"]).timestamp()
        return manual.get("episodio"), ts
    return None


def formatar_data(ts):
    if not ts:
        return "sem data confirmada"
    return datetime.fromtimestamp(ts, TZ).strftime("%d/%m/%Y às %H:%M")


def titulo(media):
    return media.get("title_english") or media.get("title") or "Sem título"


def assinatura(media, anime):
    """Impressão digital dos dados: se mudar, a página é regenerada."""
    conteudo = {
        "media": media,
        "editorial": {k: anime.get(k) for k in ("analise", "nota", "proxima_estreia")},
    }
    bruto = json.dumps(conteudo, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def casca(titulo_pagina, corpo, base=""):
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(titulo_pagina)}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 960px; margin: 0 auto; padding: 16px; line-height: 1.5; color: #222; }}
a {{ color: #0b5cad; }}
.grade {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }}
.card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; text-decoration: none; color: inherit; }}
.avisos {{ background: #fff8e1; border-left: 4px solid #f0a500; padding: 8px 16px; border-radius: 6px; }}
.rodape {{ color: #777; font-size: 0.85em; }}
</style>
</head>
<body>
<nav><a href="{base}index.html">Início</a></nav>
{corpo}
</body>
</html>
"""


def pagina_anime(media, anime, agora):
    nome = titulo(media)
    estudios = ", ".join(s["name"] for s in media.get("studios", [])) or "—"
    generos = ", ".join(g["name"] for g in media.get("genres", [])) or "—"
    sinopse = html.escape(media.get("synopsis") or "Sinopse indisponível.")
    exibicao = html.escape((media.get("broadcast") or {}).get("string") or "Não informado")
    prox = proxima_estreia(anime)
    if prox:
        ep, ts = prox
        proximo = f"Episódio {ep}: {formatar_data(ts)}" if ep else formatar_data(ts)
    else:
        proximo = "Data não confirmada"
    analise = anime.get("analise")
    if analise:
        paragrafos = "".join(f"<p>{html.escape(p)}</p>" for p in analise.split("\n\n"))
    else:
        paragrafos = "<p><em>Análise em breve.</em></p>"
    nota = anime.get("nota")
    bloco_nota = f"<p><strong>Sua nota:</strong> {nota}/10</p>" if nota is not None else ""
    url = html.escape(media.get("url") or "https://myanimelist.net")
    corpo = f"""<h1>{html.escape(nome)}</h1>
<ul>
<li><strong>Status:</strong> {html.escape(STATUS.get(media.get('status'), '—'))}</li>
<li><strong>Estúdio:</strong> {html.escape(estudios)}</li>
<li><strong>Gêneros:</strong> {html.escape(generos)}</li>
<li><strong>Episódios:</strong> {html.escape(str(media.get('episodes') or '—'))}</li>
<li><strong>Horário de exibição (original):</strong> {exibicao}</li>
<li><strong>Próxima estreia:</strong> {html.escape(proximo)}</li>
<li><strong>Nota no MyAnimeList:</strong> {html.escape(str(media.get('score') or '—'))}</li>
</ul>
<h2>Sinopse</h2>
<p>{sinopse}</p>
<h2>Análise</h2>
{bloco_nota}
{paragrafos}
<p><a href="{url}">Ficha completa no MyAnimeList</a></p>
<p class="rodape">Dados verificados em {html.escape(agora)}.</p>"""
    return casca(nome, corpo, base="../")


def pagina_inicial(cards, avisos, agora):
    if avisos:
        itens_avisos = "".join(
            f"<li><strong>{html.escape(a['texto'])}</strong> "
            f"<small>(registrado em {html.escape(a['data_registro'])})</small></li>"
            for a in avisos
        )
    else:
        itens_avisos = "<li>Nenhum aviso no momento.</li>"
    itens = "".join(
        f'<a class="card" href="anime/{html.escape(c["slug"])}.html">'
        f'<h3>{html.escape(c["nome"])}</h3>'
        f'<p>Status: {html.escape(STATUS.get(c.get("status"), "—"))}</p>'
        f'<p>{html.escape(c["proximo"])}</p></a>'
        for c in cards
    )
    corpo = f"""<section class="avisos"><h2>Avisos</h2><ul>{itens_avisos}</ul></section>
<h2>Temporada</h2>
<div class="grade">{itens}</div>
<p class="rodape">Última verificação: {html.escape(agora)}</p>"""
    return casca("Animes da temporada", corpo, base="")


def main():
    print("VERSÃO JIKAN - API:", API)
    animes = ler_json(DATA / "animes.json", [])
    estado = ler_json(DATA / "estado.json", {})
    pendentes = ler_json(DATA / "pendentes.json", [])
    avisos = ler_json(DATA / "avisos.json", [])
    agora = datetime.now(TZ).strftime("%d/%m/%Y %H:%M")
    (DOCS / "anime").mkdir(parents=True, exist_ok=True)

    for anime in animes:
        slug = anime["slug"]
        print(f"Verificando {slug}...")
        media = consultar(anime)
        if media is None:
            print("  não encontrado ou erro; mantendo os dados anteriores")
            continue

        antigo = estado.get(slug, {})
        prox = proxima_estreia(anime)
        ep_novo, at_novo = prox if prox else (None, None)

        # Mudança de data do MESMO episódio (aviso de atraso ou antecipação)
        if (
            ep_novo
            and antigo.get("ep") == ep_novo
            and antigo.get("airingAt")
            and at_novo
            and antigo["airingAt"] != at_novo
        ):
            aviso = {
                "anime": titulo(media),
                "episodio": ep_novo,
                "de": formatar_data(antigo["airingAt"]),
                "para": formatar_data(at_novo),
                "data_registro": agora,
            }
            if anime.get("fonte_oficial"):
                aviso["fonte"] = anime["fonte_oficial"]
                aviso["texto"] = (
                    f"A estreia do episódio {ep_novo} de {aviso['anime']} mudou de "
                    f"{aviso['de']} para {aviso['para']}, segundo a fonte oficial."
                )
                avisos.insert(0, aviso)
                print("  mudança de data publicada como aviso na capa")
            else:
                pendentes.append(aviso)
                print("  mudança de data enviada para revisão (sem fonte oficial)")

        assin = assinatura(media, anime)
        pagina = DOCS / "anime" / f"{slug}.html"
        if antigo.get("hash") != assin or not pagina.exists():
            pagina.write_text(pagina_anime(media, anime, agora), encoding="utf-8")
            print("  página atualizada")
        else:
            print("  sem alterações")

        if at_novo:
            resumo_prox = f"Episódio {ep_novo}: {formatar_data(at_novo)}" if ep_novo else formatar_data(at_novo)
        else:
            resumo_prox = "Data não confirmada"
        estado[slug] = {
            "slug": slug,
            "nome": titulo(media),
            "hash": assin,
            "status": media.get("status"),
            "ep": ep_novo,
            "airingAt": at_novo,
            "proximo": resumo_prox,
            "verificado": agora,
        }

    salvar_json(DATA / "estado.json", estado)
    salvar_json(DATA / "pendentes.json", pendentes)
    salvar_json(DATA / "avisos.json", avisos[:50])

    cards = [estado[a["slug"]] for a in animes if a["slug"] in estado]
    (DOCS / "index.html").write_text(pagina_inicial(cards, avisos[:10], agora), encoding="utf-8")
    print(f"Concluído. Itens aguardando revisão: {len(pendentes)}")


if __name__ == "__main__":
    main()
