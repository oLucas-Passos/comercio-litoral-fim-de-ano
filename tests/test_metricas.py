import numpy as np
import pandas as pd
import pytest
from scipy import stats

import sintetico
from litoral import metricas


@pytest.fixture(scope="module")
def modelo(painel):
    return metricas.modelo_efeitos_fixos(painel, "recebido_pj_real")


def test_efeitos_fixos_recupera_efeito_injetado(modelo):
    ef = modelo.efeitos
    # Média de k_i é 1, então o efeito médio em log é o injetado.
    for m, valor in sintetico.EFEITO_LITORAL.items():
        assert ef.at[m, "coef"] == pytest.approx(valor, abs=0.03)
        assert ef.at[m, "pct_inf"] < np.expm1(valor) < ef.at[m, "pct_sup"] + 0.03
    for m in (4, 5, 6, 7, 8, 9, 10):
        assert abs(ef.at[m, "coef"]) < 0.02


def test_efeitos_fixos_absorve_padrao_comum(modelo):
    # Natal e 13º afetam todas as cidades: não podem aparecer como efeito do litoral em novembro.
    assert abs(modelo.efeitos.at[11, "coef"]) < 0.02


def test_efeito_temporada_medio(modelo):
    esperado = np.mean(list(sintetico.EFEITO_LITORAL.values()))
    assert modelo.temporada["coef"] == pytest.approx(esperado, abs=0.02)
    assert modelo.temporada["p_valor"] < 0.001


def test_placebo_pessoa_fisica_sem_efeito(painel):
    r = metricas.modelo_efeitos_fixos(painel, "pago_pf_real")
    assert r.temporada["pct_inf"] < 0 < r.temporada["pct_sup"]


def test_efeito_uf_mes_igual_ao_principal(painel, modelo):
    r = metricas.modelo_efeitos_fixos(painel, "recebido_pj_real", tempo="uf_mes")
    assert r.temporada["coef"] == pytest.approx(modelo.temporada["coef"], abs=0.01)


def test_efeito_por_temporada_estavel(painel):
    pt = metricas.efeito_por_temporada(painel, "recebido_pj_real")
    esperado = np.mean(list(sintetico.EFEITO_LITORAL.values()))
    assert list(pt.index) == [2021, 2022, 2023, 2024]
    assert pt["coef"].to_numpy() == pytest.approx(np.full(4, esperado), abs=0.03)


def test_perfil_sazonal_deterministico():
    meses = pd.period_range("2022-04", "2024-03", freq="M")
    fator = {12: 1.5, 1: 2.0}
    painel = pd.DataFrame(
        [
            {"municipio": mun, "mes": m, "litoral": lit, "v": tam * (fator.get(m.month, 1.0) if lit else 1.0)}
            for m in meses
            for mun, lit, tam in ((1, True, 100), (2, True, 900), (3, False, 50))
        ]
    )
    p = metricas.perfil_sazonal(painel, "v").set_index(["litoral", "m"])
    assert p.loc[(True, 1), "media"] == pytest.approx(2.0)
    assert p.loc[(True, 12), "media"] == pytest.approx(1.5)
    assert p.loc[(False, 1), "media"] == pytest.approx(1.0)
    assert p.loc[(True, 1), "ciclos"] == 2
    assert p.loc[(True, 1), "ep"] == pytest.approx(0.0)


def test_indice_municipal_conta_a_mao():
    # Base: abr a out = 100 nas duas cidades. Temporada: litoral 150, interior 110.
    meses = pd.period_range("2023-04", "2024-03", freq="M")
    linhas = []
    for m in meses:
        temporada = m.month in (12, 1, 2)
        linhas.append(
            {"municipio": 1, "uf": "SP", "litoral": True, "mes": m, "v": 150.0 if temporada else 100.0}
        )
        linhas.append(
            {"municipio": 2, "uf": "SP", "litoral": False, "mes": m, "v": 110.0 if temporada else 100.0}
        )
    idx = metricas.indice_municipal(pd.DataFrame(linhas), "v").iloc[0]
    assert idx["bruto"] == pytest.approx(0.5)
    assert idx["razao_interior"] == pytest.approx(1.1)
    assert idx["alta"] == pytest.approx(1.5 / 1.1 - 1)
    assert idx["excesso"] == pytest.approx(3 * (150 - 110))


def test_indice_municipal_ordena_pela_intensidade(dados, painel):
    idx = metricas.indice_municipal(painel, "recebido_pj_real")
    media = idx.groupby("municipio")["alta"].mean()
    rho, _ = stats.spearmanr(media, dados["intensidade"].reindex(media.index))
    assert rho > 0.9
    exc = metricas.excesso_por_temporada(idx)
    assert (exc["excesso"] > 0).all() and (exc["parcela"].between(0.05, 0.4)).all()


def test_alta_por_uf(painel):
    tab = metricas.alta_por_uf(metricas.indice_municipal(painel, "recebido_pj_real"))
    assert set(tab.index) == {"SP", "BA", "SC"}  # MG não tem litoral
    assert tab.to_numpy() == pytest.approx(np.full(tab.shape, 0.23), abs=0.06)


def test_perfil_municipal_formato(painel):
    lit = painel[painel["litoral"]]
    pm = metricas.perfil_municipal(lit, "recebido_pj_real")
    assert pm.shape == (lit["municipio"].nunique(), 12)
    assert (pm[1] > pm[7]).mean() > 0.95


def test_caged_correlacao_positiva(dados, painel):
    pc = metricas.painel_caged(dados["caged"], dados["municipios"], dados["costeiros"], "2021-04", "2025-09")
    assert len(pc) == 54 * len(dados["municipios"])
    idx_c = metricas.indice_municipal(pc, "admissoes", meses_pico=(11, 12, 1), min_base=5)
    idx_p = metricas.indice_municipal(painel, "recebido_pj_real")
    corr = metricas.correlacao_pix_caged(idx_p, idx_c)
    assert corr["rho"] > 0.7 and corr["n"] == len(dados["costeiros"])


def test_correlacao_com_poucos_pontos():
    a = pd.DataFrame({"municipio": [1, 2], "alta": [0.1, 0.2]})
    assert metricas.correlacao_pix_caged(a, a)["rho"] is None
