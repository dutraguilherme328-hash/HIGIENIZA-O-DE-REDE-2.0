"""
Lê a planilha consolidada (aba CONSOLIDADO) e gera docs/dados.js com dados
AGREGADOS para o site público do GitHub Pages.

Nada de CPF/CNPJ, nome, endereço, telefone ou valor de prestador individual sai daqui:
  - contagens por UF × região × categoria × bloco × classe de rede;
  - contagens por município (total, faturam, candidatos, divergências) — sem categoria;
  - valores (R$) somente por bloco e por região, e só quando o grupo tem 3+ prestadores.

Uso:
    python scripts/gerar_dados_site.py dados/HIGIENIZACAO_REDE_CONSOLIDADA.xlsx
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

MINIMO_PARA_VALOR = 3
CANDIDATOS = list("CDEF")
DIVERGENCIAS = list("GH")
RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "docs" / "dados.js"

# Histórico da 1ª higienização (bases jan/fev 2026) — exibido para manter a referência dos 390
HISTORICO = {
    "base_inicial": 4565, "afetados": 390,
    "ondas": [
        {"onda": "1ª onda", "total": 235, "descredenciados": 152, "mantidos": 83},
        {"onda": "2ª onda", "total": 151, "descredenciados": 134, "mantidos": 11},
    ],
    "desconsiderados_estrategicos": 10,
}


def main(caminho):
    abas = pd.read_excel(caminho, sheet_name=None, dtype=str)
    df = abas["CONSOLIDADO"].fillna("")
    df["VALOR"] = pd.to_numeric(df["VALOR_FATURADO_12M"], errors="coerce").fillna(0.0)
    df["FATURA"] = (df["FATURA_12M"] == "SIM").astype(int)
    for c in ("UF", "REGIAO_SAUDE", "MUNICIPIO", "CATEGORIA_CODER", "CLASSE_REDE_EFETIVA"):
        df[c] = df[c].replace("", "NÃO INFORMADO")

    cubo = (df.groupby(["UF", "REGIAO_SAUDE", "CATEGORIA_CODER", "BLOCO", "CLASSE_REDE_EFETIVA"])
              .agg(n=("BLOCO", "size"), fat=("FATURA", "sum")).reset_index())

    mun = df.groupby(["UF", "REGIAO_SAUDE", "MUNICIPIO"]).agg(
        total=("BLOCO", "size"), fat=("FATURA", "sum"),
        cand=("BLOCO", lambda s: s.isin(CANDIDATOS).sum()),
        div=("BLOCO", lambda s: s.isin(DIVERGENCIAS).sum())).reset_index()

    def valores(por):
        g = df.groupby(por).agg(n=("BLOCO", "size"), v=("VALOR", "sum")).reset_index()
        linhas = []
        for r in g.to_dict("records"):
            r["v"] = round(float(r["v"]), 2) if r["n"] >= MINIMO_PARA_VALOR else None  # null no JSON
            del r["n"]
            linhas.append(r)
        return linhas

    legenda = {}
    if "LEGENDA" in abas:
        legenda = dict(zip(abas["LEGENDA"]["BLOCO"], abas["LEGENDA"]["DESCRICAO"]))
    info = {}
    if "INFO" in abas:
        info = dict(zip(abas["INFO"].iloc[:, 0].astype(str), abas["INFO"].iloc[:, 1].astype(str)))

    dados = {
        "data_referencia": info.get("Data de referência", ""),
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total": int(len(df)),
        "valor_total": round(float(df["VALOR"].sum()), 2),
        "legenda": legenda,
        "historico": HISTORICO,
        "cubo": [[r.UF, r.REGIAO_SAUDE, r.CATEGORIA_CODER, r.BLOCO, r.CLASSE_REDE_EFETIVA, int(r.n), int(r.fat)]
                 for r in cubo.itertuples()],
        "municipios": [[r.UF, r.REGIAO_SAUDE, r.MUNICIPIO, int(r.total), int(r.fat), int(r.cand), int(r.div)]
                       for r in mun.itertuples()],
        "valor_por_bloco": valores(["BLOCO"]),
        "valor_por_regiao_bloco": valores(["UF", "REGIAO_SAUDE", "BLOCO"]),
    }
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text("window.DADOS = " + json.dumps(dados, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"OK: {len(df)} prestadores agregados -> {SAIDA}")


if __name__ == "__main__":
    padrao = RAIZ / "dados" / "HIGIENIZACAO_REDE_CONSOLIDADA.xlsx"
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else padrao)
