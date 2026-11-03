"""Métricas de sazonalidade: perfis, modelo de efeitos fixos, índices por cidade e CAGED."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from . import config
from .transformacao import ano_ciclo

ORDEM_CICLO = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]


# --------------------------------------------------------------------------- perfis


def _indices_por_cidade(painel: pd.DataFrame, coluna: str, por: str) -> pd.DataFrame:
    """Índice de cada cidade e mês contra a média de abr a out do mesmo ciclo (ciclos completos)."""
    df = painel[["municipio", "mes", por, coluna]].copy()
    df["ciclo"] = ano_ciclo(df["mes"])
    df["m"] = df["mes"].dt.month
    n = df.groupby("ciclo")["m"].nunique()
    df = df[df["ciclo"].isin(n[n == 12].index)]
    base = df[df["m"].isin(config.MESES_BASE)].groupby(["municipio", "ciclo"])[coluna].mean().rename("base")
    df = df.join(base, on=["municipio", "ciclo"])
    df["indice"] = df[coluna] / df["base"]
    return df[df["indice"] > 0]


def perfil_sazonal(
    painel: pd.DataFrame, coluna: str, por: str = "litoral", peso: str = "cidade"
) -> pd.DataFrame:
    """Índice mensal de cada grupo em relação à média de abr a out do mesmo ciclo.

    peso="cidade": cada cidade conta igual. Calcula o índice de cada cidade,
    tira a média geométrica dentro do grupo (coerente com o modelo em log) e
    depois a média entre ciclos, com erro padrão entre ciclos. Sem isso, as
    capitais dominariam o resultado.
    peso="total": índice da soma do grupo (usado nas contagens do CAGED, que
    têm muitos zeros por cidade).
    Valor 1,30 em janeiro = 30% acima de um mês comum.
    """
    if peso == "cidade":
        df = _indices_por_cidade(painel, coluna, por)
        df["log"] = np.log(df["indice"])
        tot = df.groupby([por, "ciclo", "m"])["log"].mean().apply(np.exp).rename("indice").reset_index()
    else:
        tot = painel.groupby(["mes", por])[coluna].sum().reset_index()
        tot["ciclo"] = ano_ciclo(tot["mes"])
        tot["m"] = tot["mes"].dt.month
        n = tot.groupby(["ciclo", por])["m"].nunique()
        completos = n[n == 12].reset_index()[["ciclo", por]]
        tot = tot.merge(completos, on=["ciclo", por])
        base = tot[tot["m"].isin(config.MESES_BASE)].groupby(["ciclo", por])[coluna].mean().rename("base")
        tot = tot.join(base, on=["ciclo", por])
        tot["indice"] = tot[coluna] / tot["base"]
    g = tot.groupby([por, "m"])["indice"]
    out = pd.DataFrame({"media": g.mean(), "ep": g.std(ddof=1) / np.sqrt(g.count()), "ciclos": g.count()})
    return out.reset_index()


def indice_por_ciclo(painel: pd.DataFrame, coluna: str, por: str = "litoral") -> pd.DataFrame:
    """Série mensal: média geométrica, entre as cidades do grupo, do índice contra abr a out do ciclo."""
    df = painel[["municipio", "mes", por, coluna]].copy()
    df["ciclo"] = ano_ciclo(df["mes"])
    base = (
        df[df["mes"].dt.month.isin(config.MESES_BASE)]
        .groupby(["municipio", "ciclo"])[coluna]
        .mean()
        .rename("base")
    )
    df = df.join(base, on=["municipio", "ciclo"])
    df = df[(df[coluna] > 0) & (df["base"] > 0)]
    df["log"] = np.log(df[coluna] / df["base"])
    return df.groupby(["mes", por])["log"].mean().apply(np.exp).unstack(por)


# ------------------------------------------------------------------ efeitos fixos


def _remover_efeitos(
    df: pd.DataFrame, grupos: list[str], colunas: list[str], tol: float = 1e-10
) -> np.ndarray:
    """Projeção alternada (método de Guimarães e Portugal) para absorver vários efeitos fixos."""
    x = df[colunas].to_numpy(dtype=float).copy()
    chaves = [df[g].to_numpy() for g in grupos]
    for _ in range(500):
        anterior = x.copy()
        for chave in chaves:
            medias = pd.DataFrame(x).groupby(chave).transform("mean").to_numpy()
            x -= medias
        if np.max(np.abs(x - anterior)) < tol:
            break
    return x


@dataclass
class ResultadoEF:
    """Coeficientes litoral x mês, em log, relativos à média de abr a out."""

    efeitos: pd.DataFrame  # index mes_ano: coef, ep, ic_inf, ic_sup, pct, pct_inf, pct_sup
    temporada: dict  # efeito médio dez a fev
    n_obs: int
    n_municipios: int
    r2_within: float


def _contraste(coef: np.ndarray, cov: np.ndarray, pesos: np.ndarray) -> tuple[float, float]:
    valor = float(pesos @ coef)
    ep = float(np.sqrt(pesos @ cov @ pesos))
    return valor, ep


def _resumo_log(valor: float, ep: float) -> dict:
    z = 1.959963984540054
    return {
        "coef": valor,
        "ep": ep,
        "p_valor": float(2 * stats.norm.sf(abs(valor / ep))) if ep > 0 else float("nan"),
        "pct": float(np.expm1(valor)),
        "pct_inf": float(np.expm1(valor - z * ep)),
        "pct_sup": float(np.expm1(valor + z * ep)),
    }


def modelo_efeitos_fixos(
    painel: pd.DataFrame, coluna: str, tempo: str = "mes", mes_ref: int = 7
) -> ResultadoEF:
    """log y_it = a_i + g_t + soma_m b_m * 1[mês do ano = m] * litoral_i + e_it.

    `a_i` absorve o tamanho de cada cidade; `g_t` absorve tudo que é comum a
    todas as cidades no mês t (crescimento do Pix, inflação, Natal, 13º).
    `tempo="uf_mes"` troca `g_t` por efeitos UF x mês, comparando cada cidade
    costeira só com o interior do próprio estado. Erros padrão agrupados por
    município. Os b_m são reportados contra a média de abr a out.
    """
    df = painel[["municipio", "mes", "mes_ano", "litoral", "uf", coluna]].copy()
    df = df[df[coluna] > 0]
    df["y"] = np.log(df[coluna])
    meses = [m for m in range(1, 13) if m != mes_ref]
    nomes = [f"l{m}" for m in meses]
    for m, nome in zip(meses, nomes, strict=True):
        df[nome] = ((df["mes_ano"] == m) & df["litoral"]).astype(float)
    df["_t"] = df["mes"].astype(str) if tempo == "mes" else df["uf"] + df["mes"].astype(str)

    dados = _remover_efeitos(df, ["municipio", "_t"], ["y", *nomes])
    y, x = dados[:, 0], dados[:, 1:]
    modelo = sm.OLS(y, x).fit(cov_type="cluster", cov_kwds={"groups": df["municipio"].to_numpy()})
    b = np.asarray(modelo.params)
    v = np.asarray(modelo.cov_params())

    # Vetor completo de 12 meses (mês de referência = 0) e contraste contra abr a out.
    idx = {m: i for i, m in enumerate(meses)}
    base = np.zeros(len(meses))
    for m in config.MESES_BASE:
        if m in idx:
            base[idx[m]] += 1 / len(config.MESES_BASE)
    linhas = {}
    for m in range(1, 13):
        w = -base.copy()
        if m in idx:
            w[idx[m]] += 1
        linhas[m] = _resumo_log(*_contraste(b, v, w))
    w_temp = -base.copy()
    for m in config.MESES_TEMPORADA:
        w_temp[idx[m]] += 1 / len(config.MESES_TEMPORADA)
    ssr_total = float(((y - y.mean()) ** 2).sum())
    return ResultadoEF(
        efeitos=pd.DataFrame(linhas).T.rename_axis("mes_ano"),
        temporada=_resumo_log(*_contraste(b, v, w_temp)),
        n_obs=int(modelo.nobs),
        n_municipios=int(df["municipio"].nunique()),
        r2_within=float(1 - modelo.ssr / ssr_total) if ssr_total > 0 else float("nan"),
    )


def efeito_por_temporada(painel: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Diferenças em diferenças por temporada.

    Amostra: meses de temporada e de base. Inclui litoral x ciclo, então cada
    temporada t/t+1 é comparada com abr a out do mesmo ano t, contra o interior.
    """
    df = painel[painel["periodo"].isin(["temporada", "base"])]
    df = df[df[coluna] > 0][["municipio", "mes", "litoral", "ano_ciclo", "periodo", coluna]].copy()
    df["y"] = np.log(df[coluna])
    anos = sorted(df["ano_ciclo"].unique())
    tem_temp = df.groupby("ano_ciclo")["periodo"].apply(
        lambda s: (s == "temporada").any() and (s == "base").any()
    )
    anos = [a for a in anos if tem_temp[a]]
    df = df[df["ano_ciclo"].isin(anos)]
    temp_cols, ciclo_cols = [], []
    for a in anos:
        no_ciclo = (df["ano_ciclo"] == a) & df["litoral"]
        df[f"t{a}"] = (no_ciclo & (df["periodo"] == "temporada")).astype(float)
        temp_cols.append(f"t{a}")
        if a != anos[0]:
            df[f"c{a}"] = no_ciclo.astype(float)
            ciclo_cols.append(f"c{a}")
    df["_t"] = df["mes"].astype(str)
    cols = temp_cols + ciclo_cols
    dados = _remover_efeitos(df, ["municipio", "_t"], ["y", *cols])
    modelo = sm.OLS(dados[:, 0], dados[:, 1:]).fit(
        cov_type="cluster", cov_kwds={"groups": df["municipio"].to_numpy()}
    )
    b, v = np.asarray(modelo.params), np.asarray(modelo.cov_params())
    linhas = []
    for i, a in enumerate(anos):
        w = np.zeros(len(cols))
        w[i] = 1
        linhas.append({"ano": int(a), **_resumo_log(*_contraste(b, v, w))})
    return pd.DataFrame(linhas).set_index("ano")


# ------------------------------------------------------------ índices por cidade


def indice_municipal(
    painel: pd.DataFrame,
    coluna: str,
    meses_pico: tuple[int, ...] = config.MESES_TEMPORADA,
    min_base: float = 0.0,
    interior: str = "cidade",
) -> pd.DataFrame:
    """Alta de cada cidade costeira no pico em relação à base, descontado o interior da UF.

    Para a cidade i no ciclo t:
      bruto     = média(pico) / média(abr a out) - 1
      interior  = mesma razão nas cidades do interior da mesma UF: média geométrica
                  das razões de cada cidade (interior="cidade") ou razão da soma
                  (interior="total", para contagens com muitos zeros)
      alta      = (1 + bruto) / interior - 1
      excesso   = n_meses_pico * (média(pico) - média(base) * interior)
    `excesso` está na unidade da coluna (R$ de hoje, no caso do Pix real).
    """
    df = painel[["municipio", "uf", "litoral", "mes", coluna]].copy()
    df["m"] = df["mes"].dt.month
    df["ciclo"] = ano_ciclo(df["mes"])
    df["fase"] = np.select([df["m"].isin(meses_pico), df["m"].isin(config.MESES_BASE)], ["pico", "base"], "")
    df = df[df["fase"] != ""]
    # Só ciclos com todos os meses de base e de pico presentes.
    esperado = len(meses_pico) + len(config.MESES_BASE)
    n = df.groupby("ciclo")["m"].nunique()
    df = df[df["ciclo"].isin(n[n == esperado].index)]

    medias = df.groupby(["municipio", "uf", "litoral", "ciclo", "fase"])[coluna].mean().unstack("fase")
    medias = medias.reset_index()
    if interior == "cidade":
        # Média geométrica das razões pico/base das cidades do interior da UF.
        cid = medias[~medias["litoral"] & (medias["base"] > 0) & (medias["pico"] > 0)].copy()
        cid["log"] = np.log(cid["pico"] / cid["base"])
        ref = cid.groupby(["uf", "ciclo"])["log"].mean().apply(np.exp).rename("razao_interior").to_frame()
    else:
        ref = (
            df[~df["litoral"]]
            .groupby(["uf", "ciclo", "fase", "mes"])[coluna]
            .sum()
            .groupby(["uf", "ciclo", "fase"])
            .mean()
        ).unstack("fase")
        ref["razao_interior"] = ref["pico"] / ref["base"]
    out = medias[medias["litoral"]].join(ref["razao_interior"], on=["uf", "ciclo"])
    out = out[out["base"] > min_base]
    out["bruto"] = out["pico"] / out["base"] - 1
    out["alta"] = (out["pico"] / out["base"]) / out["razao_interior"] - 1
    out["excesso"] = len(meses_pico) * (out["pico"] - out["base"] * out["razao_interior"])
    return out.drop(columns="litoral").reset_index(drop=True)


def adicionar_excesso_tipico(indice: pd.DataFrame) -> pd.DataFrame:
    """Valor a mais de cada cidade e temporada usando a alta típica da cidade.

    alta típica = mediana das altas da cidade nas temporadas analisadas. O valor
    a mais é a parte do movimento de dez a fev explicada por ela:
      excesso_tipico = n_meses * pico * a / (1 + a)
    Usar a mediana evita que um choque isolado (uma empresa grande que muda de
    cidade, uma obra) apareça como efeito do verão.
    """
    out = indice.copy()
    tipica = out.groupby("municipio")["alta"].median().rename("alta_tipica")
    out = out.join(tipica, on="municipio")
    n_meses = len(config.MESES_TEMPORADA)
    out["excesso_tipico"] = n_meses * out["pico"] * out["alta_tipica"] / (1 + out["alta_tipica"])
    return out


def excesso_por_temporada(indice: pd.DataFrame, excluir: set[int] | frozenset = frozenset()) -> pd.DataFrame:
    """Soma do valor a mais (alta típica) das cidades costeiras e a parcela do movimento de dez a fev.

    `excluir` tira cidades da soma (no pipeline, as capitais: nelas o Pix recebido
    por empresas é dominado por fluxos entre empresas que não têm a ver com turismo).
    """
    if "excesso_tipico" not in indice:
        indice = adicionar_excesso_tipico(indice)
    sub = indice[~indice["municipio"].isin(excluir)]
    g = sub.groupby("ciclo")
    n_meses = len(config.MESES_TEMPORADA)
    out = pd.DataFrame(
        {
            "excesso": g["excesso_tipico"].sum(),
            "movimento_pico": g["pico"].sum() * n_meses,
            "cidades": g["municipio"].nunique(),
            "cidades_alta_positiva": g["alta"].apply(lambda s: int((s > 0).sum())),
            "alta_mediana": g["alta"].median(),
        }
    )
    out["parcela"] = out["excesso"] / out["movimento_pico"]
    return out


def alta_por_uf(indice: pd.DataFrame) -> pd.DataFrame:
    """Alta mediana das cidades costeiras de cada UF, por temporada (cada cidade conta igual)."""
    return indice.groupby(["uf", "ciclo"])["alta"].median().unstack("ciclo")


def perfil_municipal(painel: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Índice médio de cada mês do calendário por cidade (base: abr a out do mesmo ciclo)."""
    df = painel[["municipio", "mes", coluna]].copy()
    df["ciclo"] = ano_ciclo(df["mes"])
    df["m"] = df["mes"].dt.month
    n = df.groupby("ciclo")["m"].nunique()
    df = df[df["ciclo"].isin(n[n == 12].index)]
    base = df[df["m"].isin(config.MESES_BASE)].groupby(["municipio", "ciclo"])[coluna].mean().rename("base")
    df = df.join(base, on=["municipio", "ciclo"])
    df["indice"] = df[coluna] / df["base"]
    return df.groupby(["municipio", "m"])["indice"].mean().unstack("m")


# --------------------------------------------------------------------------- CAGED


def painel_caged(caged: pd.DataFrame, municipios: pd.DataFrame, costeiros: set[int], inicio: str, fim: str):
    """Grade completa mês x município (meses sem movimentação viram zero)."""
    cad = municipios.assign(municipio6=municipios["municipio"] // 10)
    meses = pd.period_range(inicio, fim, freq="M")
    grade = pd.MultiIndex.from_product([meses, cad["municipio6"]], names=["mes", "municipio6"]).to_frame(
        index=False
    )
    df = grade.merge(caged, on=["mes", "municipio6"], how="left").fillna(
        {"admissoes": 0, "desligamentos": 0, "saldo": 0}
    )
    df = df.merge(cad[["municipio6", "municipio", "nome", "uf", "regiao"]], on="municipio6")
    df["litoral"] = df["municipio"].isin(costeiros)
    return df


def correlacao_pix_caged(pix_idx: pd.DataFrame, caged_idx: pd.DataFrame) -> dict:
    """Correlação de Spearman entre a alta média do Pix e a alta média de admissões por cidade."""
    a = pix_idx.groupby("municipio")["alta"].mean().rename("pix")
    b = caged_idx.groupby("municipio")["alta"].mean().rename("caged")
    df = pd.concat([a, b], axis=1, join="inner").dropna()
    if len(df) < 3:
        return {"rho": None, "p_valor": None, "n": int(len(df)), "pontos": df.reset_index()}
    rho, p = stats.spearmanr(df["pix"], df["caged"])
    return {"rho": float(rho), "p_valor": float(p), "n": int(len(df)), "pontos": df.reset_index()}
