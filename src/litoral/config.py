"""Caminhos, recortes de calendário e tabelas fixas usadas no projeto."""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / "data"
BRUTOS = DADOS / "raw"
PROCESSADOS = DADOS / "processed"

DIR_PIX = BRUTOS / "pix"
ARQ_CAGED = BRUTOS / "caged_supermercados.csv"
ARQ_DEFRONTANTES = BRUTOS / "municipios_defrontantes_mar.csv"
ARQ_MUNICIPIOS = BRUTOS / "municipios.csv"
ARQ_IPCA = BRUTOS / "ipca_bcb_433.csv"
ARQ_SITE = DADOS / "litoral.json"

# O Pix começou em 16/11/2020. Os primeiros meses refletem adoção, não consumo.
INICIO_ANALISE = "2021-04"

# Temporada t/t+1 = dezembro de t, janeiro e fevereiro de t+1.
MESES_TEMPORADA = (12, 1, 2)
# Linha de base de cada temporada: abril a outubro do ano t (sem férias de verão,
# sem Natal e sem 13º salário).
MESES_BASE = (4, 5, 6, 7, 8, 9, 10)
# No CAGED o pico de contratação antecede a temporada.
MESES_PICO_CAGED = (11, 12, 1)

NOMES_MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# Classes da CNAE 2.0 do varejo alimentar (subclasses de 7 dígitos, como no CAGED).
CNAE_MERCADOS = {
    4711301: "Hipermercados",
    4711302: "Supermercados",
    4712100: "Minimercados, mercearias e armazéns",
}

UFS = {
    11: ("RO", "Norte"),
    12: ("AC", "Norte"),
    13: ("AM", "Norte"),
    14: ("RR", "Norte"),
    15: ("PA", "Norte"),
    16: ("AP", "Norte"),
    17: ("TO", "Norte"),
    21: ("MA", "Nordeste"),
    22: ("PI", "Nordeste"),
    23: ("CE", "Nordeste"),
    24: ("RN", "Nordeste"),
    25: ("PB", "Nordeste"),
    26: ("PE", "Nordeste"),
    27: ("AL", "Nordeste"),
    28: ("SE", "Nordeste"),
    29: ("BA", "Nordeste"),
    31: ("MG", "Sudeste"),
    32: ("ES", "Sudeste"),
    33: ("RJ", "Sudeste"),
    35: ("SP", "Sudeste"),
    41: ("PR", "Sul"),
    42: ("SC", "Sul"),
    43: ("RS", "Sul"),
    50: ("MS", "Centro-Oeste"),
    51: ("MT", "Centro-Oeste"),
    52: ("GO", "Centro-Oeste"),
    53: ("DF", "Centro-Oeste"),
}

# Carnaval muda de mês; quando cai em março, parte do movimento sai da temporada.
CARNAVAL = {2022: "2022-03", 2023: "2023-02", 2024: "2024-02", 2025: "2025-03", 2026: "2026-02"}

# Faixas de tamanho pelo número mediano de empresas que receberam Pix na linha de base.
FAIXAS_TAMANHO = [
    (0, 200, "até 200"),
    (200, 1000, "200 a 1.000"),
    (1000, 5000, "1.000 a 5.000"),
    (5000, float("inf"), "mais de 5.000"),
]
