import pandas as pd
import pytest

from litoral import validacao


def test_pix_sintetico_valido(dados):
    r = validacao.validar_pix(dados["pix"], dados["municipios"])
    assert r.ok, r.erros


def test_pix_duplicado_e_mes_faltando(dados):
    pix = dados["pix"]
    sem_mes = pix[pix["mes"] != pd.Period("2023-06", "M")]
    duplicado = pd.concat([sem_mes, sem_mes.head(1)])
    r = validacao.validar_pix(duplicado, dados["municipios"])
    assert any("duplicadas" in e for e in r.erros)
    assert any("2023-06" in e for e in r.erros)
    with pytest.raises(validacao.ErroValidacao):
        r.exigir()


def test_pix_codigo_desconhecido_e_negativo(dados):
    pix = dados["pix"].copy()
    pix.loc[0, "municipio"] = 9999999
    pix.loc[1, "recebido_pj"] = -1
    r = validacao.validar_pix(pix, dados["municipios"])
    assert "negativo" in " ".join(r.erros)
    assert "fora do cadastro" in " ".join(r.avisos)


def test_pix_colunas_ausentes(dados):
    r = validacao.validar_pix(dados["pix"].drop(columns="empresas"), dados["municipios"])
    assert r.erros == ["Pix: colunas ausentes ['empresas']"]


def test_litoral_em_estado_sem_mar(dados):
    mg = dados["municipios"].query("uf == 'MG'")["municipio"].iloc[0]
    r = validacao.validar_litoral(dados["costeiros"] | {mg}, dados["municipios"])
    assert any("sem litoral" in e for e in r.erros)


def test_caged_saldo_inconsistente(dados):
    caged = dados["caged"].copy()
    assert validacao.validar_caged(caged).ok
    caged.loc[0, "saldo"] += 1
    assert any("saldo" in e for e in validacao.validar_caged(caged).erros)
