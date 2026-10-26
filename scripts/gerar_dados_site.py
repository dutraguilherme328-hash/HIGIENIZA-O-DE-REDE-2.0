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
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

MINIMO_PARA_VALOR = 3
CANDIDATOS = list("CDEF")
DIVERGENCIAS = list("GH")
RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "docs" / "dados.js"
sys.path.insert(0, str(RAIZ / "scripts"))
import cripto  # noqa: E402
BASE_GEO = RAIZ / "scripts" / "base_geografica.json"

# Histórico da 1ª higienização (bases jan/fev 2026) — exibido para manter a referência dos 390
HISTORICO = {
    "base_inicial": 4565, "afetados": 390,
    "ondas": [
        {"onda": "1ª onda", "total": 235, "descredenciados": 152, "mantidos": 83},
        {"onda": "2ª onda", "total": 151, "descredenciados": 134, "mantidos": 11},
    ],
    "desconsiderados_estrategicos": 10,
}


ESPECIALIDADES = RAIZ / "dados" / "especialidades.csv"  # opcional: CPF_CNPJ;ESPECIALIDADE (fica fora do git)


def ler_especialidades():
    """Base opcional de especialidades. Aceita CPF/CNPJ com ou sem pontuação; vários por prestador viram 'A; B'."""
    if not ESPECIALIDADES.exists():
        return {}
    e = pd.read_csv(ESPECIALIDADES, sep=";", dtype=str, encoding="utf-8-sig").fillna("")
    doc, esp = e.columns[0], e.columns[1]
    e["DOC"] = e[doc].str.replace(r"\D", "", regex=True).apply(lambda d: d.zfill(11) if len(d) <= 11 else d.zfill(14))
    return e[e[esp] != ""].groupby("DOC")[esp].apply(lambda s: "; ".join(sorted(set(s.str.strip())))).to_dict()


def motivo(r):
    """Explica, em linguagem direta, por que o prestador é potencial a descredenciamento."""
    zerado = "normalizado" in r.OBSERVACOES
    m = ["Sem faturamento nos últimos 12 meses" + (" (consta na base de faturamento com valor liberado zerado)" if zerado else "")]
    if r.ANOS_CREDENCIADO:
        m.append(f"credenciado há {str(r.ANOS_CREDENCIADO).replace('.', ',')} anos" + (f" (desde {r.DATA_CREDENCIAMENTO})" if r.DATA_CREDENCIAMENTO else ""))
    qtd = lambda n, onde: f"nenhum prestador da mesma categoria faturando {onde}" if str(n) in ("0", "") else f"{n} prestador(es) da mesma categoria faturando {onde}"
    m.append(f"{qtd(r.REDE_EFETIVA_MUN, 'no município')} e {qtd(r.REDE_EFETIVA_REGIAO, 'na região de saúde').replace(' da mesma categoria faturando', '')}")
    bloco = {
        "C": "rede suficiente na localidade — a saída não compromete a cobertura",
        "D": "rede mínima na localidade — descredenciar só com substituto confirmado",
        "E": "não há outro prestador desta categoria em atividade no município — a falta de faturamento sozinha não autoriza o descredenciamento (RN 567/585); exige substituto antes",
        "F": f"efeito cumulativo — {r.CANDIDATOS_NO_GRUPO} candidatos da mesma categoria no município; retirá-los juntos rebaixaria a rede, então o descredenciamento deve ser escalonado",
    }[r.BLOCO]
    m.append(bloco)
    return "; ".join(m) + "."


def regras_do_projeto(df, data_ref):
    """Regras de escopo e de decisão aplicadas na análise, com quantos prestadores cada uma afeta.
    O texto segue o que está implementado em scripts/gerar_consolidado.py."""
    cat = df["CATEGORIA_CODER"]
    enferm = cat.str.contains("ENFERM", case=False)
    reg_med = cat == "MEDICO REGULADOR"
    propria = cat == "CLINICA IPASGO"
    fora = df["BLOCO"] == "I"
    semdoc = fora & (df["TIPO_DOC"] == "SEM DOCUMENTO") & ~(enferm | reg_med | propria)
    tecnico = fora & ~(enferm | reg_med | propria | semdoc)  # marcado como técnico pelo nome no ERP FACIL
    b = df["BLOCO"].value_counts().to_dict()
    n = lambda k: int(b.get(k, 0))
    cand = df[df["BLOCO"].isin(CANDIDATOS)]
    classe = cand["CLASSE_REDE_EFETIVA"].value_counts().to_dict()
    normalizados = int(df["OBSERVACOES"].str.contains("normalizado").sum())
    R = []
    def add(grupo, titulo, criterio, efeito, qtd=None, rotulo="prestadores", fonte="Escopo do projeto", status="Aplicada", bloco=""):
        R.append({"id": f"R{len(R) + 1:02d}", "grupo": grupo, "titulo": titulo, "criterio": criterio, "efeito": efeito,
                  "qtd": None if qtd is None else int(qtd), "rotulo": rotulo, "fonte": fonte, "status": status, "bloco": bloco})

    G1 = "1. Fora do escopo (nunca são candidatos)"
    add(G1, "Enfermeiros e derivados",
        "Categoria do BI CODER contendo \"ENFERM\": ENFERMAGEM, ENFERMEIRO REGULADOR e qualquer outra derivada.",
        "Excluídos da análise de descredenciamento, mesmo sem faturamento (bloco I).", enferm.sum(),
        fonte="Escopo do projeto — na 1ª higienização, 8 enfermeiros foram desconsiderados por decisão estratégica", bloco="I")
    add(G1, "Médico regulador", "Categoria do BI CODER = MEDICO REGULADOR.",
        "Excluídos da análise (bloco I). Função de regulação, não de assistência direta.", reg_med.sum(), bloco="I")
    add(G1, "Rede própria Ipasgo", "Categoria do BI CODER = CLINICA IPASGO (Ipasgo Clínicas).",
        "Excluídas da análise (bloco I). Não são prestadores credenciados.", propria.sum(), bloco="I")
    add(G1, "Registros técnicos do sistema", "Cadastros como \"LIB. SEM LOCAL\" e \"PRESTADOR PARA REEMBOLSO\" no ERP FACIL.",
        "Excluídos (bloco I). Não representam prestadores reais.", tecnico.sum(), bloco="I")
    add(G1, "Sem CPF/CNPJ", "Registro sem documento identificável em nenhuma das bases.",
        "Excluídos (bloco I). Não é possível cruzar com faturamento nem com o cadastro.", semdoc.sum(), bloco="I")

    G2 = "2. Protegidos (não são candidatos)"
    add(G2, "Faturou nos últimos 12 meses", "Valor liberado maior que zero na base de faturamento de 12 meses.",
        "Mantém o vínculo (bloco A). Quem fatura e não está no BI CODER vai para regularização cadastral (bloco G).", n("A") + n("G"), bloco="A / G")
    add(G2, "Credenciado há menos de 1 ano",
        f"Data de credenciamento (a mais recente entre ERP FACIL e BI CODER) a menos de 12 meses da data de referência ({data_ref}).",
        "Não é candidato: aguarda maturação e é reavaliado no próximo ciclo (bloco B).", n("B"), bloco="B")
    add(G2, "Presente em só uma base cadastral", "Sem faturamento e consta apenas no ERP FACIL ou apenas no BI CODER.",
        "Não é candidato direto: vai para saneamento cadastral FACIL × CODER (bloco H).", n("H"), bloco="H")

    G3 = "3. Candidato a descredenciamento"
    add(G3, "Critério de candidato",
        "Sem faturamento em 12 meses + credenciado há 1 ano ou mais + presente no ERP FACIL e no BI CODER + fora das exclusões do grupo 1.",
        "Entra na lista de potenciais a descredenciamento (blocos C a F).", len(cand), bloco="C–F")
    add(G3, "Rede na localidade",
        "Conta quem fatura (lente efetiva) da mesma categoria no mesmo município (IBGE): 1 = único na localidade; 2 = ele + 1 (rede mínima); 3 ou mais = rede suficiente.",
        f"Define o bloco do candidato. Entre os candidatos: {classe.get('REDE SUFICIENTE', 0)} com rede suficiente, "
        f"{classe.get('ELE + 1 (REDE MÍNIMA)', 0)} com rede mínima, {classe.get('ÚNICO NA LOCALIDADE', 0)} únicos e {classe.get('SEM REDE', 0)} sem rede faturando no município.",
        None, fonte="Metodologia do projeto (RN 567/2022 e RN 585/2023)")
    add(G3, "Rede suficiente → descredenciar", "3 ou mais prestadores da categoria faturando no município, sem contar o candidato.",
        "Bloco C — descredenciar; a saída não compromete a cobertura.", n("C"), bloco="C")
    add(G3, "Rede mínima → só com substituto", "1 ou 2 prestadores da categoria faturando no município.",
        "Bloco D — descredenciar somente com substituto confirmado.", n("D"), bloco="D")
    add(G3, "Único na localidade → manter ou substituir antes", "Nenhum outro prestador da categoria faturando no município.",
        "Bloco E — a ausência de faturamento sozinha não autoriza o descredenciamento; exige substituto na mesma localidade, com mesmas características e disponibilidade.",
        n("E"), fonte="RN 567/2022 (não hospitalar) e RN 585/2023 (hospitalar)", bloco="E")
    add(G3, "Efeito cumulativo → escalonar",
        "2 ou mais candidatos da mesma categoria no mesmo município, cuja retirada conjunta rebaixaria a classe da rede (para menos de 3).",
        "Bloco F — descredenciar em lotes escalonados, avaliando a rede a cada lote.", n("F"), bloco="F")

    G4 = "4. Normas e garantia de atendimento"
    add(G4, "Substituição de prestadores", "Não hospitalares: RN 567/2022. Hospitalares: RN 585/2023. Contratos: Lei 13.003/2014.",
        "Indicada em cada candidato (coluna Norma aplicável).", None, fonte="ANS / Lei 13.003/2014")
    add(G4, "Garantia de atendimento (mapa)",
        "Ordem da RN 566/2022: no município → em município limítrofe → em outro município da região de saúde (transporte custeado, art. 4º, §2º) → fora da região (transporte de ida e volta).",
        "Usada no mapa para medir onde a cobertura piora após o descredenciamento. Regiões de saúde: SES-GO.", None, fonte="RN 566/2022")

    G5 = "5. Tratamento dos dados e prioridade"
    add(G5, "Normalização de CPF/CNPJ",
        "Restaura zeros à esquerda; números de 11 a 13 dígitos são testados como CPF e como CNPJ contra o cadastro.",
        "Evita faturamento \"órfão\" e falsos candidatos.", normalizados, rotulo="prestadores com documento corrigido")
    add(G5, "Categoria oficial", "A categoria vem do BI CODER (base curada pela CODER), separada do tipo do ERP FACIL.",
        "Usada para rede na localidade, exclusões e cobertura.", None)
    add(G5, "Score de prioridade (0–100)",
        "+40 sem faturamento em 12 meses; +15 credenciado há 5+ anos (ou +8 de 2 a 5 anos); +30 rede efetiva suficiente no município (ou +12 rede mínima); "
        "+10 rede suficiente na região de saúde; +5 sem contato cadastrado; −15 efeito cumulativo.",
        "Ordena os candidatos: quanto maior, mais seguro e prioritário o descredenciamento.", None)

    G6 = "6. Regras da 1ª higienização não aplicadas nesta fase"
    add(G6, "Ação administrativa nos últimos 12 meses",
        "Na 1ª versão, quem solicitou ou executou serviços no período não era candidato direto.",
        "Não aplicada: as bases desta fase não trazem solicitações nem execuções. Pode ser incluída quando essa base for enviada.",
        None, fonte="1ª higienização (bases jan/fev 2026)", status="Pendente de base")
    return R


def lista_candidatos(df):
    esp = ler_especialidades()
    c = df[df["BLOCO"].isin(CANDIDATOS)].copy()
    resumo = {"C": "Sem faturamento · rede suficiente", "D": "Sem faturamento · rede mínima",
              "E": "Sem faturamento · único na localidade", "F": "Sem faturamento · efeito cumulativo"}
    linhas = []
    for r in c.sort_values(["SCORE_PRIORIDADE", "NOME"], ascending=[False, True]).itertuples():
        linhas.append([
            r.NOME, r.CATEGORIA_CODER, esp.get(r.DOC, ""), r.MUNICIPIO, r.UF, r.REGIAO_SAUDE,
            r.BLOCO, int(float(r.SCORE_PRIORIDADE or 0)), resumo[r.BLOCO], motivo(r),
            r.FATORES_SCORE, r.ACAO_RECOMENDADA, r.NORMA_APLICAVEL, r.CLASSE_REDE_EFETIVA,
        ])
    return linhas, bool(esp)


def nivel(m, rede, base):
    """Nível de garantia de atendimento (RN 566/2022) do município m, dado o conjunto de municípios com rede."""
    if m in rede:
        return 1  # há prestador no próprio município
    g = base[m]
    if any(v in rede for v in g["vizinhos"]):
        return 2  # só em município limítrofe
    if any(o in rede for o in base if base[o]["regiao"] == g["regiao"]):
        return 3  # só na região de saúde (não limítrofe) — transporte custeado
    if rede:
        return 4  # só fora da região de saúde — transporte ida e volta
    return 0      # nenhum prestador da categoria em GO/DF


def cobertura_rn566(df):
    """Para cada categoria: nível por município (antes, depois de descredenciar C–F, e só rede que fatura).
    Sai como 3 strings de dígitos na ordem de base_geografica.json. Não leva contagens por município×categoria."""
    base = {g["ibge"]: g for g in json.loads(BASE_GEO.read_text(encoding="utf-8"))}
    ordem = list(base)
    rede = df[(df["CATEGORIA_CODER"] != "NÃO INFORMADO") & (df["BLOCO"] != "I") & df["IBGE_MUN"].isin(base)]
    cobertura = {}
    for cat, g in rede.groupby("CATEGORIA_CODER"):
        por_mun = g.groupby("IBGE_MUN").agg(cad=("BLOCO", "size"),
                                            cand=("BLOCO", lambda s: s.isin(CANDIDATOS).sum()),
                                            efe=("FATURA", "sum"))
        antes = set(por_mun.index[por_mun["cad"] > 0])
        depois = set(por_mun.index[por_mun["cad"] - por_mun["cand"] > 0])
        efetiva = set(por_mun.index[por_mun["efe"] > 0])
        cobertura[cat] = ["".join(str(nivel(m, s, base)) for m in ordem) for s in (antes, depois, efetiva)]
    return {
        "geo": [[m, base[m]["nome"], base[m]["uf"], base[m]["regiao"], [ordem.index(v) for v in base[m]["vizinhos"]]] for m in ordem],
        "cobertura": cobertura,
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

    df["IBGE_MUN"] = df["IBGE_MUN"].fillna("")
    mun = df.groupby(["UF", "REGIAO_SAUDE", "MUNICIPIO", "IBGE_MUN"]).agg(
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
        "municipios": [[r.UF, r.REGIAO_SAUDE, r.MUNICIPIO, int(r.total), int(r.fat), int(r.cand), int(r.div), r.IBGE_MUN]
                       for r in mun.itertuples()],
        **cobertura_rn566(df),
        "candidatos_campos": ["nome", "categoria", "especialidade", "municipio", "uf", "regiao", "bloco", "score",
                              "resumo", "motivo", "fatores", "acao", "norma", "classe_rede"],
        "valor_por_bloco": valores(["BLOCO"]),
        "valor_por_regiao_bloco": valores(["UF", "REGIAO_SAUDE", "BLOCO"]),
    }
    dados["candidatos"], dados["tem_especialidade"] = lista_candidatos(df)
    dados["regras"] = regras_do_projeto(df, info.get("Data de referência", ""))
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    # os dados vão CIFRADOS (AES-256-GCM) — só quem tem usuário e senha consegue ler no navegador
    texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
    SAIDA.write_text("window.DADOS_CIFRADO = " + json.dumps(cripto.cifrar(texto, cripto.chave_site())) + ";\n", encoding="utf-8")
    # força o navegador a buscar a versão nova dos dados (evita cache antigo do GitHub Pages)
    versao = datetime.now().strftime("%Y%m%d%H%M")
    pagina = RAIZ / "docs" / "index.html"
    html = pagina.read_text(encoding="utf-8")
    html = re.sub(r'src="(dados|mapa|acesso)\.js(\?v=\d+)?"', lambda m: f'src="{m.group(1)}.js?v={versao}"', html)
    pagina.write_text(html, encoding="utf-8")
    print(f"OK: {len(df)} prestadores agregados -> {SAIDA} (versão {versao})")


if __name__ == "__main__":
    padrao = RAIZ / "dados" / "HIGIENIZACAO_REDE_CONSOLIDADA.xlsx"
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else padrao)
