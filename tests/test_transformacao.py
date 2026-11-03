import numpy as np
import pandas as pd
import pytest

from litoral import transformacao as tr


def test_indice_ipca_base_no_ultimo_mes():
    ipca = pd.Series([1.0, 1.0, 1.0], index=pd.period_range("2024-01", periods=3, freq="M"))
    idx = tr.indice_ipca(ipca)
    assert idx.iloc[-1] == pytest.approx(1.0)
    assert idx.iloc[0] == pytest.approx(1 / 1.01**2)


def test_ano_ciclo_e_classificacao():
    meses = pd.PeriodIndex(["2024-03", "2024-04", "2024-12", "2025-01", "2025-11"], freq="M")
    assert tr.ano_ciclo(meses).tolist() == [2023, 2024, 2024, 2024, 2025]
    assert tr.classificar_mes(meses).tolist() == ["outro", "base", "temporada", "temporada", "outro"]
    assert tr.rotulo_temporada(2024) == "2024/25"


def test_montar_painel_exclui_cidade_com_mes_zerado(dados):
    pix = dados["pix"].copy()
    alvo = sorted(dados["costeiros"])[0]
    pix.loc[(pix["municipio"] == alvo) & (pix["mes"] == pd.Period("2022-05", "M")), "recebido_pj"] = 0
    painel, cob = tr.montar_painel(pix, dados["municipios"], dados["costeiros"], dados["ipca"])
    assert alvo not in set(painel["municipio"])
    assert cob["excluidos"] == 1 and cob["excluidos_litoral"] == 1


def test_montar_painel_deflaciona(painel):
    ultimo = painel[painel["mes"] == painel["mes"].max()]
    # IPCA sintético vai até 2025-12, então o último mês do Pix ainda tem deflator < 1.
    assert (ultimo["deflator"] < 1).all()
    np.testing.assert_allclose(painel["recebido_pj_real"], painel["recebido_pj"] / painel["deflator"])


def test_montar_painel_repete_ipca_quando_falta(dados):
    ipca = dados["ipca"][dados["ipca"].index <= pd.Period("2025-06", "M")]
    painel, cob = tr.montar_painel(dados["pix"], dados["municipios"], dados["costeiros"], ipca)
    assert cob["ipca_repetido"] == ["2025-07", "2025-08", "2025-09"]
    assert painel["deflator"].notna().all()


def test_temporadas_completas(painel):
    # Dados de 2021-04 a 2025-09: temporadas 2021/22 a 2024/25.
    assert tr.temporadas_completas(painel) == [2021, 2022, 2023, 2024]
    assert tr.ciclos_completos(painel) == [2021, 2022, 2023, 2024]


def test_faixa_tamanho():
    assert tr.faixa_tamanho(50) == "até 200"
    assert tr.faixa_tamanho(1000) == "1.000 a 5.000"
    assert tr.faixa_tamanho(1e6) == "mais de 5.000"
