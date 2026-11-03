"""Dados sintéticos com efeitos conhecidos, usados nos testes.

O efeito de temporada no litoral é injetado em log e varia de cidade para
cidade (intensidade k_i). Os testes verificam se o pipeline recupera esses
valores. Nada daqui vai para o site publicado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Efeito médio no litoral em log, por mês do ano, relativo a abr a out (zero).
EFEITO_LITORAL = {12: np.log(1.10), 1: np.log(1.40), 2: np.log(1.20)}
# Padrão comum a todas as cidades (Natal, 13º); deve ser absorvido pelo efeito de tempo.
COMUM = {11: 0.04, 12: 0.15, 1: -0.05, 3: 0.02}

UFS_TESTE = [(35, "SP", "Sudeste"), (29, "BA", "Nordeste"), (42, "SC", "Sul"), (31, "MG", "Sudeste")]


def cadastro(n_interior_por_uf: int = 60, n_litoral_por_uf: int = 15) -> tuple[pd.DataFrame, set[int]]:
    linhas, costeiros = [], set()
    for cod_uf, uf, regiao in UFS_TESTE:
        n_lit = 0 if uf == "MG" else n_litoral_por_uf
        for j in range(n_interior_por_uf + n_lit):
            codigo = cod_uf * 100000 + (j + 1) * 10 + (j % 10)
            linhas.append(
                {
                    "municipio": codigo,
                    "nome": f"Cidade {uf} {j + 1}",
                    "uf": uf,
                    "regiao": regiao,
                    "lat": 0.0,
                    "lon": 0.0,
                    "capital": j == 0,
                }
            )
            if j >= n_interior_por_uf:
                costeiros.add(codigo)
    return pd.DataFrame(linhas), costeiros


def ipca(inicio: str = "2020-01", fim: str = "2025-12") -> pd.Series:
    meses = pd.period_range(inicio, fim, freq="M")
    return pd.Series(0.4, index=meses, name="ipca")


def pix(
    municipios: pd.DataFrame,
    costeiros: set[int],
    inicio: str = "2021-04",
    fim: str = "2025-09",
    ruido: float = 0.05,
    semente: int = 7,
) -> tuple[pd.DataFrame, pd.Series]:
    """Pix recebido por empresas e pago por pessoas, em R$ correntes."""
    rng = np.random.default_rng(semente)
    meses = pd.period_range(inicio, fim, freq="M")
    t = np.arange(len(meses))
    crescimento = np.exp(0.02 * t)  # adoção do Pix
    inflacao = 1.004 ** (t + 15)  # 0,4% a.m., alinhado ao ipca() desde 2020-01
    comum = np.array([COMUM.get(m.month, 0.0) for m in meses])
    intensidade = pd.Series(
        rng.uniform(0.5, 1.5, len(municipios)) * municipios["municipio"].isin(costeiros).to_numpy(),
        index=municipios["municipio"],
    )
    linhas = []
    for _, mun in municipios.iterrows():
        tamanho = np.exp(rng.normal(15, 1))
        k = intensidade[mun["municipio"]]
        efeito = np.array([k * EFEITO_LITORAL.get(m.month, 0.0) for m in meses])
        log_pj = np.log(tamanho) + np.log(crescimento) + comum + efeito + rng.normal(0, ruido, len(meses))
        log_pf = np.log(tamanho * 0.6) + np.log(crescimento) + comum + rng.normal(0, ruido, len(meses))
        empresas = int(np.exp(rng.normal(6, 1)))
        for i, mes in enumerate(meses):
            linhas.append(
                {
                    "mes": mes,
                    "municipio": mun["municipio"],
                    "recebido_pj": float(np.exp(log_pj[i]) * inflacao[i]),
                    "transacoes_pj": int(np.exp(log_pj[i]) / 80),
                    "empresas": empresas,
                    "pago_pf": float(np.exp(log_pf[i]) * inflacao[i]),
                    "pagadores_pf": empresas * 10,
                }
            )
    return pd.DataFrame(linhas), intensidade


def caged(
    municipios: pd.DataFrame,
    intensidade: pd.Series,
    inicio: str = "2021-04",
    fim: str = "2025-09",
    semente: int = 11,
) -> pd.DataFrame:
    """Admissões no varejo alimentar com alta em nov a jan proporcional à intensidade da cidade."""
    rng = np.random.default_rng(semente)
    meses = pd.period_range(inicio, fim, freq="M")
    pico = {11: 0.6, 12: 0.8, 1: 0.4}
    linhas = []
    for _, mun in municipios.iterrows():
        k = intensidade[mun["municipio"]]
        media = rng.uniform(15, 60)
        for mes in meses:
            lam = media * np.exp(k * pico.get(mes.month, 0.0))
            adm = int(rng.poisson(lam))
            desl = int(rng.poisson(media))
            if adm == 0 and desl == 0:
                continue
            linhas.append(
                {
                    "mes": mes,
                    "municipio6": mun["municipio"] // 10,
                    "admissoes": adm,
                    "desligamentos": desl,
                    "saldo": adm - desl,
                }
            )
    return pd.DataFrame(linhas)


def tudo(**kw) -> dict:
    municipios, costeiros = cadastro(**{k: v for k, v in kw.items() if k.startswith("n_")})
    p, intensidade = pix(municipios, costeiros)
    return {
        "municipios": municipios,
        "costeiros": costeiros,
        "pix": p,
        "caged": caged(municipios, intensidade),
        "ipca": ipca(),
        "intensidade": intensidade,
    }
