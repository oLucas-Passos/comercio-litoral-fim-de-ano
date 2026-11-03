"""Orquestra leitura, validação, métricas e exportação (CSV processados e JSON do site)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from . import config, ingestao, metricas, transformacao, validacao
from .metricas import ORDEM_CICLO

# Cidades muito pequenas têm índices instáveis; ficam fora do ranking, não do modelo.
MIN_EMPRESAS_RANKING = 100
# Para o CAGED, média mínima de admissões por mês na base para calcular a alta da cidade.
MIN_ADMISSOES_BASE = 5


@dataclass
class Entradas:
    pix: pd.DataFrame
    caged: pd.DataFrame | None
    municipios: pd.DataFrame
    costeiros: set[int]
    ipca: pd.Series


def carregar() -> Entradas:
    caged = ingestao.ler_caged() if config.ARQ_CAGED.exists() else None
    return Entradas(
        pix=ingestao.ler_pix(),
        caged=caged,
        municipios=ingestao.ler_municipios(),
        costeiros=ingestao.ler_defrontantes(),
        ipca=ingestao.ler_ipca(),
    )


# ------------------------------------------------------------------- utilidades


def _num(x, casas: int = 4):
    if x is None:
        return None
    if isinstance(x, (np.integer, int)):
        return int(x)
    x = float(x)
    return None if math.isnan(x) or math.isinf(x) else round(x, casas)


def _lista(valores, casas: int = 4) -> list:
    return [_num(v, casas) for v in valores]


def _perfil_json(perfil: pd.DataFrame, por: str = "litoral") -> dict:
    out = {}
    for grupo, sub in perfil.groupby(por):
        sub = sub.set_index("m").reindex(ORDEM_CICLO)
        chave = ("litoral" if grupo else "interior") if por == "litoral" else str(grupo)
        out[chave] = {
            "media": _lista(sub["media"]),
            "ep": _lista(sub["ep"]),
            "ciclos": _num(sub["ciclos"].min()),
        }
    return out


# --------------------------------------------------------------------- análise


def analisar(e: Entradas) -> dict:
    """Roda todas as métricas e devolve o dicionário exportado para o site."""
    rel = validacao.validar_pix(e.pix, e.municipios).exigir()
    rel_lit = validacao.validar_litoral(e.costeiros, e.municipios).exigir()
    avisos = rel.avisos + rel_lit.avisos
    cadastro = set(e.municipios["municipio"])
    pix = e.pix[e.pix["municipio"].isin(cadastro)]
    costeiros = e.costeiros & cadastro

    painel, cobertura = transformacao.montar_painel(pix, e.municipios, costeiros, e.ipca)
    col = "recebido_pj_real"
    temporadas = transformacao.temporadas_completas(painel)
    rotulos = {a: transformacao.rotulo_temporada(a) for a in temporadas}

    # Tamanho da cidade: mediana de empresas recebedoras nos meses de base.
    empresas = painel[painel["periodo"] == "base"].groupby("municipio")["empresas"].median()

    # Perfis descritivos
    perfil = metricas.perfil_sazonal(painel, col)
    perfil_lit = painel[painel["litoral"]]
    perfil_pf = pd.concat(
        [
            metricas.perfil_sazonal(perfil_lit, col).assign(serie="recebido_pj"),
            metricas.perfil_sazonal(perfil_lit, "pago_pf_real").assign(serie="pago_pf"),
        ]
    )
    serie = metricas.indice_por_ciclo(painel, col)

    # Modelo principal e por temporada
    ef = metricas.modelo_efeitos_fixos(painel, col)
    por_temp = metricas.efeito_por_temporada(painel, col)

    # Robustez: efeito médio dez a fev em especificações alternativas
    grandes = set(empresas[empresas >= MIN_EMPRESAS_RANKING].index)
    variacoes = {
        "Principal: valor real recebido por empresas": (painel, col, "mes"),
        "Comparando só com o interior do mesmo estado": (painel, col, "uf_mes"),
        "Sem as capitais": (painel[~painel["capital"]], col, "mes"),
        f"Só cidades com {MIN_EMPRESAS_RANKING} empresas ou mais": (
            painel[painel["municipio"].isin(grandes)],
            col,
            "mes",
        ),
        "Número de transações em vez de valor": (painel, "transacoes_pj", "mes"),
        "Sem a temporada 2021/22": (painel[painel["ano_ciclo"] != 2021], col, "mes"),
        "Pago por moradores (pessoa física)": (painel, "pago_pf_real", "mes"),
    }
    robustez = []
    for nome, (dados, coluna, tempo) in variacoes.items():
        if coluna not in dados or dados.loc[dados["litoral"], "municipio"].nunique() < 2:
            continue
        r = metricas.modelo_efeitos_fixos(dados, coluna, tempo=tempo)
        robustez.append(
            {"nome": nome, **{k: _num(v) for k, v in r.temporada.items()}, "municipios": r.n_municipios}
        )

    # Cidades
    idx = metricas.indice_municipal(painel, col)
    idx = metricas.adicionar_excesso_tipico(idx)
    capitais = set(e.municipios.loc[e.municipios["capital"], "municipio"])
    excesso = metricas.excesso_por_temporada(idx, excluir=capitais)
    perfis_cidade = metricas.perfil_municipal(painel[painel["litoral"]], col)
    perfil_interior_uf = metricas.perfil_sazonal(painel[~painel["litoral"]], col, por="uf")
    por_uf = metricas.alta_por_uf(idx)

    cad = e.municipios.set_index("municipio")
    ultimo = max(temporadas) if temporadas else None
    cidades = []
    for mun, sub in idx.groupby("municipio"):
        sub = sub.set_index("ciclo")
        n_emp = float(empresas.get(mun, np.nan))
        ult = sub.loc[ultimo] if ultimo in sub.index else None
        cidades.append(
            {
                "codigo": int(mun),
                "nome": cad.at[mun, "nome"],
                "uf": cad.at[mun, "uf"],
                "capital": bool(cad.at[mun, "capital"]),
                "empresas": _num(n_emp, 0),
                "faixa": transformacao.faixa_tamanho(n_emp) if not math.isnan(n_emp) else None,
                "ranking": bool(n_emp >= MIN_EMPRESAS_RANKING),
                "alta_tipica": _num(sub["alta"].median()),
                "alta": _num(None if ult is None else ult["alta"]),
                "bruto": _num(None if ult is None else ult["bruto"]),
                "excesso": _num(None if ult is None else ult["excesso_tipico"], 0),
                "base": _num(None if ult is None else ult["base"], 0),
                "temporadas": {rotulos[a]: _num(sub.at[a, "alta"]) for a in temporadas if a in sub.index},
                "perfil": _lista(perfis_cidade.loc[mun].reindex(ORDEM_CICLO))
                if mun in perfis_cidade.index
                else None,
            }
        )

    # Tamanho: alta mediana por faixa
    tam = pd.DataFrame([c for c in cidades if c["faixa"]])
    por_faixa = []
    if len(tam):
        for _, _, faixa in config.FAIXAS_TAMANHO:
            s = tam.loc[tam["faixa"] == faixa, "alta_tipica"].dropna()
            if len(s):
                por_faixa.append(
                    {
                        "faixa": faixa,
                        "cidades": int(len(s)),
                        "mediana": _num(s.median()),
                        "q1": _num(s.quantile(0.25)),
                        "q3": _num(s.quantile(0.75)),
                    }
                )

    caged = analisar_caged(e, painel, idx) if e.caged is not None else None
    if caged:
        avisos += caged.pop("avisos")

    pico = ef.efeitos["pct"].astype(float).idxmax()
    ult_exc = excesso.loc[ultimo] if ultimo in excesso.index else None
    return {
        "gerado_em": date.today().isoformat(),
        "cobertura": cobertura,
        "avisos": avisos,
        "meses_ciclo": [config.NOMES_MES[m - 1] for m in ORDEM_CICLO],
        "kpis": {
            "temporada": rotulos.get(ultimo),
            "excesso": _num(None if ult_exc is None else ult_exc["excesso"], 0),
            "parcela": _num(None if ult_exc is None else ult_exc["parcela"]),
            "alta_temporada": _num(ef.temporada["pct"]),
            "alta_inf": _num(ef.temporada["pct_inf"]),
            "alta_sup": _num(ef.temporada["pct_sup"]),
            "mes_pico": config.NOMES_MES[int(pico) - 1],
            "alta_pico": _num(ef.efeitos.at[pico, "pct"]),
            "cidades_litoral": cobertura["municipios_litoral"],
        },
        "perfil": _perfil_json(perfil),
        "perfil_pf": _perfil_json(perfil_pf, por="serie"),
        "efeitos": {
            "pct": _lista(ef.efeitos.loc[ORDEM_CICLO, "pct"]),
            "inf": _lista(ef.efeitos.loc[ORDEM_CICLO, "pct_inf"]),
            "sup": _lista(ef.efeitos.loc[ORDEM_CICLO, "pct_sup"]),
            "p": _lista(ef.efeitos.loc[ORDEM_CICLO, "p_valor"], 6),
            "coef": _lista(ef.efeitos.loc[ORDEM_CICLO, "coef"]),
            "ep": _lista(ef.efeitos.loc[ORDEM_CICLO, "ep"]),
            "temporada": {k: _num(v, 6) for k, v in ef.temporada.items()},
            "n_obs": ef.n_obs,
            "n_municipios": ef.n_municipios,
            "r2_within": _num(ef.r2_within),
        },
        "por_temporada": [
            {
                "temporada": rotulos.get(int(a), transformacao.rotulo_temporada(int(a))),
                **{k: _num(v) for k, v in r.items()},
            }
            for a, r in por_temp.iterrows()
        ],
        "serie": {
            "meses": [str(m) for m in serie.index],
            "litoral": _lista(serie.get(True, pd.Series(dtype=float))),
            "interior": _lista(serie.get(False, pd.Series(dtype=float))),
            "carnaval": list(config.CARNAVAL.values()),
        },
        "excesso": [
            {
                "temporada": rotulos[int(a)],
                "excesso": _num(r["excesso"], 0),
                "parcela": _num(r["parcela"]),
                "movimento": _num(r["movimento_pico"], 0),
                "cidades": int(r["cidades"]),
                "cidades_alta": int(r["cidades_alta_positiva"]),
                "alta_mediana": _num(r["alta_mediana"]),
            }
            for a, r in excesso.iterrows()
            if int(a) in rotulos
        ],
        "ufs": {
            "temporadas": [rotulos[a] for a in temporadas],
            "linhas": [
                {"uf": uf, "valores": _lista([linha.get(a) for a in temporadas])}
                for uf, linha in por_uf.iterrows()
            ],
        },
        "interior_uf": {
            uf: _lista(sub.set_index("m").reindex(ORDEM_CICLO)["media"])
            for uf, sub in perfil_interior_uf.groupby("uf")
        },
        "cidades": sorted(cidades, key=lambda c: -(c["alta_tipica"] or -9)),
        "tamanho": por_faixa,
        "robustez": robustez,
        "caged": caged,
        "parametros": {
            "meses_temporada": list(config.MESES_TEMPORADA),
            "meses_base": list(config.MESES_BASE),
            "meses_pico_caged": list(config.MESES_PICO_CAGED),
            "min_empresas_ranking": MIN_EMPRESAS_RANKING,
            "min_admissoes_base": MIN_ADMISSOES_BASE,
            "cnae": {str(k): v for k, v in config.CNAE_MERCADOS.items()},
        },
        "_tabelas": {"painel": painel, "indice": idx, "excesso": excesso, "efeitos": ef.efeitos},
    }


def analisar_caged(e: Entradas, painel: pd.DataFrame, idx_pix: pd.DataFrame) -> dict:
    rel = validacao.validar_caged(e.caged).exigir()
    inicio, fim = painel["mes"].min(), min(painel["mes"].max(), e.caged["mes"].max())
    pc = metricas.painel_caged(
        e.caged, e.municipios, e.costeiros & set(e.municipios["municipio"]), str(inicio), str(fim)
    )
    perfil = metricas.perfil_sazonal(pc, "admissoes", peso="total")
    idx = metricas.indice_municipal(
        pc, "admissoes", meses_pico=config.MESES_PICO_CAGED, min_base=MIN_ADMISSOES_BASE, interior="total"
    )
    corr = metricas.correlacao_pix_caged(idx_pix, idx)
    cad = e.municipios.set_index("municipio")
    pontos = corr.pop("pontos")
    agregado = pc.groupby(["litoral", pc["mes"].dt.month])["admissoes"].sum()
    return {
        "avisos": rel.avisos,
        "fim": str(fim),
        "perfil": _perfil_json(perfil),
        "admissoes_ano": {
            "litoral": int(agregado.get(True, pd.Series(dtype=int)).sum()),
            "interior": int(agregado.get(False, pd.Series(dtype=int)).sum()),
        },
        "cidades": int(idx["municipio"].nunique()),
        "alta_mediana": _num(idx.groupby("municipio")["alta"].mean().median()),
        "correlacao": {k: _num(v, 6) for k, v in corr.items()},
        "pontos": [
            {
                "codigo": int(r["municipio"]),
                "nome": cad.at[r["municipio"], "nome"],
                "uf": cad.at[r["municipio"], "uf"],
                "pix": _num(r["pix"]),
                "caged": _num(r["caged"]),
            }
            for _, r in pontos.iterrows()
        ],
    }


def salvar(resultado: dict) -> None:
    tabelas = resultado.pop("_tabelas")
    config.PROCESSADOS.mkdir(parents=True, exist_ok=True)
    painel = tabelas["painel"]
    colunas = [
        "mes",
        "municipio",
        "uf",
        "litoral",
        "empresas",
        "recebido_pj",
        "recebido_pj_real",
        "pago_pf",
        "pago_pf_real",
        "transacoes_pj",
    ]
    painel[colunas].round({"recebido_pj_real": 0, "pago_pf_real": 0, "recebido_pj": 0, "pago_pf": 0}).to_csv(
        config.PROCESSADOS / "painel_pix.csv.gz", index=False
    )
    tabelas["indice"].to_csv(config.PROCESSADOS / "indice_cidades.csv", index=False)
    tabelas["excesso"].to_csv(config.PROCESSADOS / "excesso_temporadas.csv")
    tabelas["efeitos"].to_csv(config.PROCESSADOS / "efeitos_mes.csv")
    texto = json.dumps(resultado, ensure_ascii=False, separators=(",", ":"))
    config.ARQ_SITE.write_text(texto, encoding="utf-8")
    resumo = {k: resultado[k] for k in ("cobertura", "kpis", "robustez", "excesso", "por_temporada")}
    resumo["efeitos"] = {k: v for k, v in resultado["efeitos"].items()}
    (config.PROCESSADOS / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2), "utf-8")


def executar() -> dict:
    resultado = analisar(carregar())
    for aviso in resultado["avisos"]:
        print("aviso:", aviso)
    salvar(resultado)
    k = resultado["kpis"]
    print(f"Temporada {k['temporada']}: alta média dez a fev no litoral {k['alta_temporada']:+.1%}")
    return resultado
