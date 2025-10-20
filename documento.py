# documento.py
# Descrição: Modelo de Dados com bancos de tabelas, figuras e fórmulas globais para o projeto.

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from referencia import Referencia, Livro, Artigo, Site
from formula import Formula

@dataclass
class Tabela:
    titulo: str = ""
    fonte: str = ""
    dados: List[List[str]] = field(default_factory=list)
    estilo_borda: str = 'abnt'
    numero: int = 0

@dataclass
class Figura:
    titulo: str = ""
    fonte: str = ""
    caminho_original: str = ""
    caminho_processado: str = ""
    largura_cm: float = 12.0
    numero: int = 0

@dataclass
class Configuracoes:
    tipo_trabalho: str = "Trabalho de Conclusão de Curso (TCC)"
    instituicao: str = "Universidade Estadual do Piauí (UESPI)"
    curso: str = "Ciência da Computação"
    modalidade_curso: str = "Bacharelado"
    titulo_pretendido: str = "Bacharel"
    cidade: str = "Araioses"
    estado: str = "MA"
    ano: int = datetime.now().year
    mes: str = datetime.now().strftime("%B").capitalize()
    
    # --- CAMPOS FINAIS PARA O BRASÃO ---
    posicao_brasao: str = "Nenhum"
    # Brasão Esquerdo
    caminho_brasao_esquerdo_original: str = ""
    caminho_brasao_esquerdo_processado: str = ""
    tamanho_brasao_esquerdo_cm: float = 2.5
    # Brasão Direito
    caminho_brasao_direito_original: str = ""
    caminho_brasao_direito_processado: str = ""
    tamanho_brasao_direito_cm: float = 2.5

@dataclass
class Autor:
    nome_completo: str

@dataclass
class Capitulo:
    titulo: str
    conteudo: str = ""
    is_template_item: bool = False
    filhos: List['Capitulo'] = field(default_factory=list)
    pai: Optional['Capitulo'] = field(default=None, repr=False)

    def adicionar_filho(self, filho: 'Capitulo'):
        filho.pai = self
        self.filhos.append(filho)
    
    def to_dict(self):
        return {
            "titulo": self.titulo,
            "conteudo": self.conteudo,
            "is_template_item": self.is_template_item,
            "filhos": [filho.to_dict() for filho in self.filhos],
        }

    @classmethod
    def from_dict(cls, data):
        capitulo = cls(
            titulo=data['titulo'],
            conteudo=data.get('conteudo', ''),
            is_template_item=data.get('is_template_item', False)
        )
        for filho_data in data.get('filhos', []):
            filho = Capitulo.from_dict(filho_data)
            capitulo.adicionar_filho(filho)
        return capitulo

class DocumentoABNT:
    def __init__(self):
        self.configuracoes: Configuracoes = Configuracoes()
        self.titulo: str = ""
        self.autores: List[Autor] = []
        self.orientador: str = ""
        self.resumo: str = ""
        self.palavras_chave: str = ""
        self.estrutura_textual = Capitulo(titulo="Raiz do Documento")
        self.referencias: List[Referencia] = []
        
        self.banco_tabelas: List[Tabela] = []
        self.banco_figuras: List[Figura] = []
        self.banco_formulas: List[Formula] = [] # NOVO

    def ordenar_referencias(self):
        self.referencias.sort(key=lambda ref: ref.get_chave_ordenacao())
        
    def to_dict(self):
        refs_serializadas = []
        for ref in self.referencias:
            ref_dict = ref.__dict__
            ref_dict['tipo_ref'] = ref.tipo
            refs_serializadas.append(ref_dict)

        return {
            "configuracoes": self.configuracoes.__dict__,
            "titulo": self.titulo,
            "autores": [a.__dict__ for a in self.autores],
            "orientador": self.orientador,
            "resumo": self.resumo,
            "palavras_chave": self.palavras_chave,
            "estrutura_textual": self.estrutura_textual.to_dict(),
            "referencias": refs_serializadas,
            "banco_tabelas": [t.__dict__ for t in self.banco_tabelas],
            "banco_figuras": [f.__dict__ for f in self.banco_figuras],
            "banco_formulas": [f.__dict__ for f in self.banco_formulas] # NOVO
        }

    @classmethod
    def from_dict(cls, data):
        doc = cls()
        doc.configuracoes = Configuracoes(**data.get('configuracoes', {}))
        doc.titulo = data.get('titulo', '')
        doc.autores = [Autor(**a) for a in data.get('autores', [])]
        doc.orientador = data.get('orientador', '')
        doc.resumo = data.get('resumo', '')
        doc.palavras_chave = data.get('palavras_chave', '')
        doc.estrutura_textual = Capitulo.from_dict(data.get('estrutura_textual', {"titulo": "Raiz"}))
        
        doc.banco_tabelas = [Tabela(**t) for t in data.get('banco_tabelas', [])]
        doc.banco_figuras = [Figura(**f) for f in data.get('banco_figuras', [])]
        doc.banco_formulas = [Formula(**f) for f in data.get('banco_formulas', [])] # NOVO

        for ref_data in data.get('referencias', []):
            tipo = ref_data.pop('tipo_ref', None)
            
            ref_data.pop('tipo', None)
            
            if tipo == 'Livro':
                doc.referencias.append(Livro(**ref_data))
            elif tipo == 'Artigo':
                doc.referencias.append(Artigo(**ref_data))
            elif tipo == 'Site':
                doc.referencias.append(Site(**ref_data))
        return doc