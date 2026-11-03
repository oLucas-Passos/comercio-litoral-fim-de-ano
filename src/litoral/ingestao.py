"""Leitura dos arquivos brutos: Pix por município (BCB), CAGED, municípios e IPCA."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

from . import config

# Colunas da API TransacoesPixPorMunicipio (Olinda/BCB) que o projeto usa.
COLUNAS_PIX = {
    "AnoMes": "mes",
    "Municipio_Ibge": "municipio",
    "VL_RecebedorPJ": "recebido_pj",
    "QT_RecebedorPJ": "transacoes_pj",
    "QT_PES_RecebedorPJ": "empresas",
    "VL_PagadorPF": "pago_pf",
    "QT_PES_PagadorPF": "pagadores_pf",
}


def _mes(valores: pd.Series) -> pd.PeriodIndex:
    texto = valores.astype(str).str.replace("-", "", regex=False).str[:6]
    return pd.PeriodIndex(pd.to_datetime(texto, format="%Y%m"), freq="M")


def ler_pix(pasta: Path = config.DIR_PIX) -> pd.DataFrame:
    """Junta os arquivos mensais baixados por scripts/baixar_pix.py.

    Retorna uma linha por (mes, municipio), com valores em R$ correntes.
    """
    arquivos = sorted(pasta.glob("*.csv*"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum arquivo de Pix em {pasta}. Rode scripts/baixar_pix.py.")
    partes = [pd.read_csv(a, usecols=lambda c: c in COLUNAS_PIX) for a in arquivos]
    df = pd.concat(partes, ignore_index=True).rename(columns=COLUNAS_PIX)
    # A API traz uma linha por mês sem município (transações sem localização); fica de fora.
    df = df.dropna(subset=["municipio"])
    df["mes"] = _mes(df["mes"])
    df["municipio"] = df["municipio"].astype(int)
    return df.sort_values(["municipio", "mes"]).reset_index(drop=True)


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", base.lower())


def ler_caged(caminho: Path = config.ARQ_CAGED) -> pd.DataFrame:
    """Movimentações no varejo alimentar agregadas por mês e município.

    O CAGED usa o código IBGE de 6 dígitos (sem o verificador). Aqui ele é
    mantido em `municipio6` e a junção com o Pix usa `municipio // 10`.
    """
    df = pd.read_csv(caminho)
    df["mes"] = _mes(df["mes"])
    df["municipio6"] = df["municipio6"].astype(int)
    for c in ("admissoes", "desligamentos", "saldo"):
        df[c] = df[c].astype(int)
    return df.sort_values(["municipio6", "mes"]).reset_index(drop=True)


def agregar_microdados_caged(micro: pd.DataFrame) -> pd.DataFrame:
    """Agrega um arquivo CAGEDMOV (já lido) para o varejo alimentar.

    Aceita os cabeçalhos originais com acento (`competênciamov`,
    `saldomovimentação`) ou já normalizados.
    """
    micro = micro.rename(columns={c: _sem_acento(c) for c in micro.columns})
    sub = micro[micro["subclasse"].astype(int).isin(config.CNAE_MERCADOS)]
    saldo = sub["saldomovimentacao"].astype(int)
    out = (
        pd.DataFrame(
            {
                "mes": sub["competenciamov"].astype(int),
                "municipio6": sub["municipio"].astype(int),
                "admissoes": (saldo > 0).astype(int),
                "desligamentos": (saldo < 0).astype(int),
                "saldo": saldo,
            }
        )
        .groupby(["mes", "municipio6"], as_index=False)
        .sum()
    )
    return out


def ler_municipios(caminho: Path = config.ARQ_MUNICIPIOS) -> pd.DataFrame:
    """Cadastro de municípios (código IBGE, nome, UF, região, coordenadas da sede)."""
    df = pd.read_csv(caminho)
    df = df.rename(columns={"codigo_ibge": "municipio", "latitude": "lat", "longitude": "lon"})
    df["uf"] = df["codigo_uf"].map(lambda c: config.UFS[c][0])
    df["regiao"] = df["codigo_uf"].map(lambda c: config.UFS[c][1])
    df["capital"] = df["capital"].astype(bool)
    return df[["municipio", "nome", "uf", "regiao", "lat", "lon", "capital"]]


def ler_defrontantes(caminho: Path = config.ARQ_DEFRONTANTES) -> set[int]:
    """Códigos IBGE (7 dígitos) da lista de municípios defrontantes com o mar.

    A coluna com os códigos é encontrada pelo conteúdo, para aceitar tanto o
    CSV gerado pelo script quanto uma planilha exportada do IBGE.
    """
    df = pd.read_csv(caminho, dtype=str) if caminho.suffix == ".csv" else pd.read_excel(caminho, dtype=str)
    for coluna in df.columns:
        valores = df[coluna].dropna().str.strip()
        if len(valores) and valores.str.fullmatch(r"\d{7}").mean() > 0.9:
            return set(valores[valores.str.fullmatch(r"\d{7}")].astype(int))
    raise ValueError(f"Nenhuma coluna com códigos IBGE de 7 dígitos em {caminho.name}")


def ler_ipca(caminho: Path = config.ARQ_IPCA) -> pd.Series:
    """Variação mensal do IPCA em % (SGS 433)."""
    df = pd.read_csv(caminho)
    serie = pd.Series(
        df["ipca_variacao_mensal_pct"].astype(float).values,
        index=pd.PeriodIndex(df["mes"], freq="M"),
        name="ipca",
    )
    if serie.index.has_duplicates:
        raise ValueError("Meses duplicados no IPCA")
    return serie.sort_index()
