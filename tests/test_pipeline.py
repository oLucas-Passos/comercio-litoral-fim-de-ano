import json

import pytest

from litoral import config, pipeline


@pytest.fixture(scope="module")
def resultado(dados):
    e = pipeline.Entradas(
        pix=dados["pix"],
        caged=dados["caged"],
        municipios=dados["municipios"],
        costeiros=dados["costeiros"],
        ipca=dados["ipca"],
    )
    return pipeline.analisar(e)


def test_kpis(resultado):
    k = resultado["kpis"]
    assert k["temporada"] == "2024/25"
    assert k["mes_pico"] == "jan"
    assert k["alta_inf"] < k["alta_temporada"] < k["alta_sup"]
    assert k["excesso"] > 0


def test_estrutura_para_o_site(resultado):
    assert resultado["meses_ciclo"][0] == "abr" and resultado["meses_ciclo"][-1] == "mar"
    assert len(resultado["efeitos"]["pct"]) == 12
    assert set(resultado["perfil"]) == {"litoral", "interior"}
    assert set(resultado["perfil_pf"]) == {"recebido_pj", "pago_pf"}
    assert len(resultado["serie"]["meses"]) == len(resultado["serie"]["litoral"])
    assert [t["temporada"] for t in resultado["por_temporada"]] == [
        "2021/22",
        "2022/23",
        "2023/24",
        "2024/25",
    ]
    assert all(len(c["perfil"]) == 12 for c in resultado["cidades"])
    assert resultado["caged"]["correlacao"]["rho"] > 0.5
    nomes = [r["nome"] for r in resultado["robustez"]]
    assert "Pago por moradores (pessoa física)" in nomes and len(nomes) == 7


def test_cidades_ordenadas_por_alta(resultado):
    altas = [c["alta_tipica"] for c in resultado["cidades"]]
    assert altas == sorted(altas, reverse=True)


def test_sem_caged(dados):
    e = pipeline.Entradas(
        pix=dados["pix"],
        caged=None,
        municipios=dados["municipios"],
        costeiros=dados["costeiros"],
        ipca=dados["ipca"],
    )
    assert pipeline.analisar(e)["caged"] is None


def test_salvar_gera_json_valido(resultado, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROCESSADOS", tmp_path / "processed")
    monkeypatch.setattr(config, "ARQ_SITE", tmp_path / "litoral.json")
    pipeline.salvar(dict(resultado))
    site = json.loads((tmp_path / "litoral.json").read_text("utf-8"))
    assert "_tabelas" not in site
    assert (tmp_path / "processed" / "indice_cidades.csv").exists()
    assert (
        json.loads((tmp_path / "processed" / "resumo.json").read_text("utf-8"))["kpis"]["mes_pico"] == "jan"
    )
