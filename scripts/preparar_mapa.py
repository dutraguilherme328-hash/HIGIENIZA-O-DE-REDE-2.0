"""
Prepara a base geográfica do painel (rodar só quando mudar a malha municipal ou as regiões).

Entradas (públicas):
  scripts/geo/geojs-52-mun.json  malha municipal de Goiás (IBGE, via github.com/tbrugz/geodata-br)
  scripts/geo/geojs-53-mun.json  Distrito Federal
  scripts/regioes_saude_go.txt   regiões de saúde da SES-GO

Saídas:
  scripts/base_geografica.json   município, UF, região de saúde e municípios limítrofes
  docs/mapa.js                   contornos simplificados (SVG) de municípios e regiões

Requer: pip install shapely
"""
import json
import re
import unicodedata
from pathlib import Path

from shapely.geometry import MultiPolygon, shape
from shapely.validation import make_valid
from shapely.ops import unary_union
from shapely.strtree import STRtree

RAIZ = Path(__file__).resolve().parent.parent
GEO = RAIZ / "scripts" / "geo"
LARGURA = 900
TOLERANCIA = 0.006  # graus (~600 m) — só para desenho; vizinhança usa a malha original


def chave(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper().replace("'", " ")
    return " ".join(re.sub(r"[^A-Z ]", " ", s).split())


def reparar(g):
    """Corrige polígonos inválidos da malha (ex.: Mineiros) sem perder área — buffer(0) encolhia o município."""
    if g.is_valid:
        return g
    v = make_valid(g)
    polys = [p for p in getattr(v, "geoms", [v]) if p.geom_type in ("Polygon", "MultiPolygon")]
    partes = [q for p in polys for q in getattr(p, "geoms", [p])]
    return MultiPolygon(partes) if len(partes) > 1 else partes[0]


def ler_regioes():
    reg = {}
    for linha in (RAIZ / "scripts" / "regioes_saude_go.txt").read_text(encoding="utf-8").splitlines():
        if not linha.strip() or linha.startswith("#"):
            continue
        regiao, municipios = linha.split(":", 1)
        for m in municipios.split(";"):
            reg[chave(m)] = chave(regiao)
    return reg


def main():
    regioes = ler_regioes()
    feats = []
    for uf, arq in (("GO", "geojs-52-mun.json"), ("DF", "geojs-53-mun.json")):
        for f in json.loads((GEO / arq).read_text(encoding="utf-8"))["features"]:
            nome = f["properties"]["name"]
            regiao = "DISTRITO FEDERAL" if uf == "DF" else regioes.get(chave(nome))
            if regiao is None:
                raise SystemExit(f"Município sem região de saúde: {nome}")
            feats.append({"ibge": f["properties"]["id"], "nome": nome, "uf": uf, "regiao": regiao,
                          "geom": reparar(shape(f["geometry"]))})

    # vizinhança (limítrofes) na malha original
    geoms = [f["geom"] for f in feats]
    arvore = STRtree(geoms)
    for i, f in enumerate(feats):
        # tolerância de ~1 m; se a malha tiver fresta (sem nenhum vizinho), tenta ~200 m
        for folga in (1e-5, 0.002):
            area = f["geom"].buffer(folga)
            f["vizinhos"] = sorted(feats[j]["ibge"] for j in arvore.query(area) if j != i and area.intersects(geoms[j]))
            if f["vizinhos"]:
                break

    # projeção simples (equiretangular com correção de latitude) para SVG
    minx, miny, maxx, maxy = unary_union(geoms).bounds
    import math
    fx = math.cos(math.radians((miny + maxy) / 2))
    escala = LARGURA / ((maxx - minx) * fx)
    altura = round((maxy - miny) * escala)

    def caminho(g):
        g = g.simplify(TOLERANCIA, preserve_topology=True)
        partes = []
        for poly in getattr(g, "geoms", [g]):
            for anel in [poly.exterior, *poly.interiors]:
                pts = [(round((x - minx) * fx * escala, 1), round((maxy - y) * escala, 1)) for x, y in anel.coords]
                partes.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
        return "".join(partes)

    def centro(g):
        p = g.representative_point()
        return [round((p.x - minx) * fx * escala, 1), round((maxy - p.y) * escala, 1)]

    por_regiao = {}
    for f in feats:
        por_regiao.setdefault(f["regiao"], []).append(f["geom"])

    mapa = {
        "largura": LARGURA, "altura": altura,
        "municipios": {f["ibge"]: {"d": caminho(f["geom"]), "c": centro(f["geom"])} for f in feats},
        "regioes": {r: {"d": caminho(unary_union(gs)), "c": centro(unary_union(gs))} for r, gs in por_regiao.items()},
    }
    (RAIZ / "docs" / "mapa.js").write_text("window.MAPA = " + json.dumps(mapa, ensure_ascii=False, separators=(",", ":")) + ";\n",
                                           encoding="utf-8")
    base = [{k: f[k] for k in ("ibge", "nome", "uf", "regiao", "vizinhos")} for f in feats]
    (RAIZ / "scripts" / "base_geografica.json").write_text(json.dumps(base, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{len(feats)} municípios, {len(por_regiao)} regiões de saúde, mapa {LARGURA}×{altura}")


if __name__ == "__main__":
    main()
