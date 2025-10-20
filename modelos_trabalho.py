# modelos_trabalho.py
# Descrição: Centraliza as estruturas de capítulos para os diferentes modelos de trabalho acadêmico.
# Para modificar ou adicionar templates, edite o dicionário ESTRUTURAS_MODELO abaixo.

ESTRUTURAS_MODELO = {
    "Trabalho de Conclusão de Curso (TCC)": [
        "INTRODUÇÃO",
        "FUNDAMENTAÇÃO TEÓRICA",
        "METODOLOGIA",
        "ANÁLISE E RESULTADOS",
        "CONCLUSÃO"
    ],
    "Artigo Científico": [
        "INTRODUÇÃO",
        "MATERIAIS E MÉTODOS",
        "RESULTADOS",
        "DISCUSSÃO",
        "CONCLUSÃO"
    ],
    "Dissertação de Mestrado": [
        "INTRODUÇÃO",
        "REVISÃO DA LITERATURA",
        "METODOLOGIA",
        "RESULTADOS",
        "DISCUSSÃO",
        "CONCLUSÃO"
    ],
    "Tese de Doutorado": [
        "INTRODUÇÃO",
        "ESTADO DA ARTE",
        "PROPOSTA DO TRABALHO",
        "VALIDAÇÃO E RESULTADOS",
        "DISCUSSÃO",
        "CONCLUSÃO GERAL"
    ]
}

def get_nomes_modelos():
    """Retorna uma lista com os nomes de todos os modelos disponíveis."""
    return list(ESTRUTURAS_MODELO.keys())

def get_estrutura_por_nome(nome_modelo: str):
    """Retorna a lista de capítulos para um determinado nome de modelo."""
    return ESTRUTURAS_MODELO.get(nome_modelo, [])