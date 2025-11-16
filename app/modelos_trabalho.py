# modelos_trabalho.py
# Descrição: Centraliza as estruturas de capítulos para os diferentes modelos.
# Versão 2.0: Modificado para usar uma estrutura hierárquica (dicionários)
# para suportar subtópicos (subcapítulos) nos modelos.

def _criar_capitulo(titulo: str, filhos: list = None):
    """Função helper para criar a estrutura de dicionário do capítulo."""
    if filhos is None:
        filhos = []
    return {
        "titulo": titulo,
        "is_template_item": True, # Marca como um capítulo de modelo
        "conteudo": "",
        "filhos": filhos
    }

# Agora ESTRUTURAS_MODELO armazena uma lista de dicionários,
# que é o formato exato que o Capitulo.from_dict() espera.
ESTRUTURAS_MODELO = {
    
    "TCC (Completo e Detalhado)": [
        _criar_capitulo("1. INTRODUÇÃO", [
            _criar_capitulo("1.1 Contextualização do Tema"),
            _criar_capitulo("1.2 Problema de Pesquisa"),
            _criar_capitulo("1.3 Hipótese (se houver)"),
            _criar_capitulo("1.4 Delimitação do Tema"),
            _criar_capitulo("1.5 Justificativa"),
            _criar_capitulo("1.6 Objetivos", [
                _criar_capitulo("1.6.1 Objetivo Geral"),
                _criar_capitulo("1.6.2 Objetivos Específicos")
            ]),
            _criar_capitulo("1.7 Estrutura do Trabalho")
        ]),
        _criar_capitulo("2. REFERENCIAL TEÓRICO", [
            _criar_capitulo("2.1 Conceitos Fundamentais"),
            _criar_capitulo("2.2 Trabalhos Relacionados"),
            _criar_capitulo("2.3 Tecnologias e Ferramentas")
        ]),
        _criar_capitulo("3. METODOLOGIA", [
            _criar_capitulo("3.1 Tipo de Pesquisa"),
            _criar_capitulo("3.2 Procedimentos Metodológicos"),
            _criar_capitulo("3.3 Etapas de Desenvolvimento"),
            _criar_capitulo("3.4 Critérios de Avaliação")
        ]),
        _criar_capitulo("4. DESENVOLVIMENTO E RESULTADOS", [
            _criar_capitulo("4.1 Arquitetura do Sistema"),
            _criar_capitulo("4.2 Componentes e Módulos"),
            _criar_capitulo("4.3 Testes e Experimentos"),
            _criar_capitulo("4.4 Resultados Obtidos"),
            _criar_capitulo("4.5 Discussão dos Resultados")
        ]),
        _criar_capitulo("5. CONCLUSÃO", [
            _criar_capitulo("5.1 Síntese do Trabalho e Alcance dos Objetivos"),
            _criar_capitulo("5.2 Limitações Encontradas"),
            _criar_capitulo("5.3 Sugestões para Trabalhos Futuros")
        ])
    ],

    "Trabalho de Conclusão de Curso (TCC)": [
        _criar_capitulo("INTRODUÇÃO"),
        _criar_capitulo("FUNDAMENTAÇÃO TEÓRICA"),
        _criar_capitulo("METODOLOGIA"),
        _criar_capitulo("ANÁLISE E RESULTADOS"),
        _criar_capitulo("CONCLUSÃO")
    ],
    
    "Artigo Científico": [
        _criar_capitulo("INTRODUÇÃO"),
        _criar_capitulo("MATERIAIS E MÉTODOS"),
        _criar_capitulo("RESULTADOS"),
        _criar_capitulo("DISCUSSÃO"),
        _criar_capitulo("CONCLUSÃO")
    ],
    
    "Dissertação de Mestrado": [
        _criar_capitulo("INTRODUÇÃO"),
        _criar_capitulo("REVISÃO DA LITERATURA"),
        _criar_capitulo("METODOLOGIA"),
        _criar_capitulo("RESULTADOS"),
        _criar_capitulo("DISCUSSÃO"),
        _criar_capitulo("CONCLUSÃO")
    ],
    
    "Tese de Doutorado": [
        _criar_capitulo("INTRODUÇÃO"),
        _criar_capitulo("ESTADO DA ARTE"),
        _criar_capitulo("PROPOSTA DO TRABALHO"),
        _criar_capitulo("VALIDAÇÃO E RESULTADOS"),
        _criar_capitulo("DISCUSSÃO"),
        _criar_capitulo("CONCLUSÃO GERAL")
    ]
}

def get_nomes_modelos():
    """Retorna uma lista com os nomes de todos os modelos disponíveis."""
    # Isso continua funcionando da mesma forma
    return list(ESTRUTURAS_MODELO.keys())

def get_estrutura_por_nome(nome_modelo: str):
    """Retorna a lista de capítulos (agora como dicts) para um nome de modelo."""
    # Isso também continua funcionando, mas agora retorna list[dict]
    return ESTRUTURAS_MODELO.get(nome_modelo, [])