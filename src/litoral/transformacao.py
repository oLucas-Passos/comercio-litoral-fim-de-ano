"""Montagem do painel município x mês: deflação, classificação e calendário de temporadas."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def indice_ipca(variacao_pct: pd.Series, base: pd.Period | None = None) -> pd.Series:
    """Número-índice do IPCA com valor 1 no mês-base (padrão: último mês da série)."""
    indice = (1 + variacao_pct / 100).cumprod()
    base = indice.index.max() if base is None else base
    return indice / indice.loc[base]


def ano_ciclo(mes: pd.PeriodIndex | pd.Series) -> np.ndarray:
    """Ano do ciclo abr(t) a mar(t+1). Jan a mar pertencem ao ciclo do ano anterior."""
    m = pd.PeriodIndex(mes)
    return np.where(m.month >= 4, m.year, m.year - 1)


def rotulo_temporada(ano: int) -> str:
    return f"{ano}/{str(ano + 1)[-2:]}"


def classificar_mes(mes: pd.PeriodIndex | pd.Series) -> np.ndarray:
    """'temporada', 'base' ou 'outro' para cada mês."""
    m = pd.PeriodIndex(mes).month
    return np.select(
        [np.isin(m, config.MESES_TEMPORADA), np.isin(m, config.MESES_BASE)], ["temporada", "base"], "outro"
    )


def montar_painel(
    pix: pd.DataFrame,
    municipios: pd.DataFrame,
    costeiros: set[int],
    ipca: pd.Series,
    inicio: str = config.INICIO_ANALISE,
) -> tuple[pd.DataFrame, dict]:
    """Painel analítico com valores reais e marcação de litoral.

    Municípios com algum mês sem Pix recebido por empresas saem do painel,
    porque o modelo usa log do valor. O número excluído é devolvido para o
    relatório de cobertura.
    """
    df = pix[pix["mes"] >= pd.Period(inicio, "M")].merge(municipios, on="municipio", how="left")
    df["litoral"] = df["municipio"].isin(costeiros)

    indice = indice_ipca(ipca)
    faltando = sorted(set(df["mes"]) - set(indice.index))
    if faltando:
        # IPCA sai depois do Pix: repete o último índice e registra.
        indice = indice.reindex(sorted(set(indice.index) | set(faltando))).ffill()
    df["deflator"] = df["mes"].map(indice).astype(float)
    for col in ("recebido_pj", "pago_pf"):
        df[f"{col}_real"] = df[col] / df["deflator"]

    n_meses = df["mes"].nunique()
    completos = df[df["recebido_pj"] > 0].groupby("municipio")["mes"].nunique()
    manter = set(completos[completos == n_meses].index)
    excluidos = df.loc[~df["municipio"].isin(manter), ["municipio", "litoral"]].drop_duplicates()
    df = df[df["municipio"].isin(manter)].copy()

    df["ano_ciclo"] = ano_ciclo(df["mes"])
    df["periodo"] = classificar_mes(df["mes"])
    df["mes_ano"] = df["mes"].dt.month

    cobertura = {
        "meses": int(n_meses),
        "inicio": str(df["mes"].min()),
        "fim": str(df["mes"].max()),
        "municipios": int(df["municipio"].nunique()),
        "municipios_litoral": int(df.loc[df["litoral"], "municipio"].nunique()),
        "excluidos": int(len(excluidos)),
        "excluidos_litoral": int(excluidos["litoral"].sum()),
        "ipca_repetido": [str(m) for m in faltando],
    }
    return df.reset_index(drop=True), cobertura


def ciclos_completos(painel: pd.DataFrame) -> list[int]:
    """Anos de ciclo com os 12 meses (abr a mar) presentes."""
    n = painel.groupby("ano_ciclo")["mes"].nunique()
    return sorted(int(a) for a in n[n == 12].index)


def temporadas_completas(painel: pd.DataFrame) -> list[int]:
    """Anos t cuja temporada t/t+1 e cuja base (abr a out de t) estão completas."""
    meses = set(painel["mes"])
    out = []
    for ano in sorted(painel["ano_ciclo"].unique()):
        necessarios = [pd.Period(f"{ano}-{m:02d}", "M") for m in config.MESES_BASE + (12,)]
        necessarios += [pd.Period(f"{ano + 1}-{m:02d}", "M") for m in (1, 2)]
        if all(m in meses for m in necessarios):
            out.append(int(ano))
    return out


def totais_por_grupo(painel: pd.DataFrame, coluna: str, por: str | None = None) -> pd.DataFrame:
    """Soma mensal da coluna por grupo (litoral / interior), opcionalmente por UF."""
    chaves = ["mes", "litoral"] + ([por] if por else [])
    return painel.groupby(chaves)[coluna].sum().reset_index()


def faixa_tamanho(empresas: float) -> str:
    for lo, hi, rotulo in config.FAIXAS_TAMANHO:
        if lo <= empresas < hi:
            return rotulo
    return config.FAIXAS_TAMANHO[-1][2]
