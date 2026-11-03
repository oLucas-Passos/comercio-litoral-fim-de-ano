import pandas as pd
import pytest

from litoral import ingestao


def test_ler_pix_renomeia_e_converte_mes(tmp_path):
    pd.DataFrame(
        {
            "AnoMes": [202401, 202401],
            "Municipio_Ibge": [3550308, 3304557],
            "Municipio": ["SP", "RJ"],
            "VL_RecebedorPJ": [10.0, 5.0],
            "QT_RecebedorPJ": [2, 1],
            "QT_PES_RecebedorPJ": [1, 1],
            "VL_PagadorPF": [3.0, 2.0],
            "QT_PES_PagadorPF": [4, 3],
            "Regiao": ["SE", "SE"],
        }
    ).to_csv(tmp_path / "202401.csv.gz", index=False)
    df = ingestao.ler_pix(tmp_path)
    assert list(df.columns) == [
        "mes",
        "municipio",
        "recebido_pj",
        "transacoes_pj",
        "empresas",
        "pago_pf",
        "pagadores_pf",
    ]
    assert df["mes"].iloc[0] == pd.Period("2024-01", "M")
    assert df["municipio"].tolist() == [3304557, 3550308]


def test_ler_pix_sem_arquivos(tmp_path):
    with pytest.raises(FileNotFoundError):
        ingestao.ler_pix(tmp_path)


def test_agregar_microdados_caged_aceita_cabecalho_com_acento():
    micro = pd.DataFrame(
        {
            "competênciamov": [202312] * 5,
            "município": [355030, 355030, 355030, 330455, 330455],
            "subclasse": [4711302, 4711302, 4711302, 4712100, 5611201],
            "saldomovimentação": [1, 1, -1, 1, 1],
        }
    )
    out = ingestao.agregar_microdados_caged(micro).set_index("municipio6")
    assert out.loc[355030, "admissoes"] == 2 and out.loc[355030, "desligamentos"] == 1
    assert out.loc[330455, "admissoes"] == 1  # o restaurante (5611201) fica de fora
    assert out.loc[355030, "saldo"] == 1


def test_ler_defrontantes_encontra_coluna_de_codigos(tmp_path):
    caminho = tmp_path / "lista.csv"
    pd.DataFrame(
        {"UF": ["SP", "SP"], "CD_MUN": ["3520400", "3555406"], "NM": ["Ilhabela", "Ubatuba"]}
    ).to_csv(caminho, index=False)
    assert ingestao.ler_defrontantes(caminho) == {3520400, 3555406}


def test_ler_defrontantes_sem_codigos(tmp_path):
    caminho = tmp_path / "lista.csv"
    pd.DataFrame({"nome": ["a", "b"]}).to_csv(caminho, index=False)
    with pytest.raises(ValueError):
        ingestao.ler_defrontantes(caminho)


def test_ler_municipios(tmp_path):
    caminho = tmp_path / "m.csv"
    pd.DataFrame(
        {
            "codigo_ibge": [3555406],
            "nome": ["Ubatuba"],
            "latitude": [-23.4],
            "longitude": [-45.1],
            "capital": [0],
            "codigo_uf": [35],
        }
    ).to_csv(caminho, index=False)
    m = ingestao.ler_municipios(caminho).iloc[0]
    assert (m["uf"], m["regiao"], bool(m["capital"])) == ("SP", "Sudeste", False)


def test_ler_ipca_rejeita_meses_duplicados(tmp_path):
    caminho = tmp_path / "ipca.csv"
    pd.DataFrame({"mes": ["2024-01", "2024-01"], "ipca_variacao_mensal_pct": [0.4, 0.5]}).to_csv(
        caminho, index=False
    )
    with pytest.raises(ValueError):
        ingestao.ler_ipca(caminho)
