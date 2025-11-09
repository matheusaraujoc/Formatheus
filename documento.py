# documento.py
# Descrição: Define as estruturas de dados centrais do projeto.
# CORREÇÃO: Adicionado de volta o método to_dict() que
# faltava na classe Formula.

from __future__ import annotations
from typing import Literal

class Configuracoes:
    """Armazena as configurações globais do documento."""
    def __init__(self):
        self.tipo_trabalho: str = "Trabalho Acadêmico (Padrão)"
        self.instituicao: str = "Nome da Instituição"
        self.curso: str = "Nome do Curso"
        self.modalidade_curso: str = "Bacharelado" 
        self.titulo_pretendido: str = "Bacharel"
        self.cidade: str = "Cidade"
        self.ano: int = 2025
        self.posicao_brasao: str = "Nenhum"
        self.caminho_brasao_esquerdo_original: str = ""
        self.caminho_brasao_esquerdo_processado: str = ""
        self.tamanho_brasao_esquerdo_cm: float = 3.0
        self.caminho_brasao_direito_original: str = ""
        self.caminho_brasao_direito_processado: str = ""
        self.tamanho_brasao_direito_cm: float = 3.0

    @classmethod
    def from_dict(cls, data: dict) -> Configuracoes:
        config = cls()
        for key, value in data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config

    def to_dict(self) -> dict:
        """Converte a instância em um dicionário para salvar."""
        return self.__dict__

class Autor:
    """Representa um autor do trabalho."""
    def __init__(self, nome_completo: str):
        self.nome_completo = nome_completo

    def get_nome_citacao(self) -> str:
        partes = self.nome_completo.split()
        if not partes: return ""
        primeiro_nome = partes[0]
        sobrenome = partes[-1]
        meio = " ".join(partes[1:-1])
        if meio:
            return f"{sobrenome.upper()}, {primeiro_nome} {meio}"
        return f"{sobrenome.upper()}, {primeiro_nome}"

    @classmethod
    def from_dict(cls, data: dict) -> Autor:
        return cls(nome_completo=data.get('nome_completo', ''))
        
    def to_dict(self) -> dict:
        """Converte a instância em um dicionário para salvar."""
        return self.__dict__

class Capitulo:
    """Representa um nó na estrutura hierárquica do documento."""
    def __init__(self, titulo: str, conteudo: str = "", is_template_item: bool = True):
        self.titulo: str = titulo
        self.conteudo: str = conteudo
        self.filhos: list[Capitulo] = []
        self.pai: Capitulo | None = None
        self.is_template_item: bool = is_template_item

    def adicionar_filho(self, filho: Capitulo):
        filho.pai = self
        self.filhos.append(filho)

    @classmethod
    def from_dict(cls, data: dict) -> Capitulo:
        capitulo = cls(
            titulo=data.get('titulo', 'Sem Título'),
            conteudo=data.get('conteudo', ''), 
            is_template_item=data.get('is_template_item', True)
        )
        for filho_data in data.get('filhos', []):
            capitulo.adicionar_filho(cls.from_dict(filho_data))
        return capitulo

    def to_dict(self) -> dict:
        """Converte o capítulo e seus filhos recursivamente em um dicionário."""
        return {
            "titulo": self.titulo,
            "conteudo": self.conteudo,
            "is_template_item": self.is_template_item,
            "filhos": [filho.to_dict() for filho in self.filhos]
        }

class Tabela:
    """Armazena os dados de uma tabela."""
    def __init__(self, titulo: str = "", fonte: str = "", dados: list[list[str]] | None = None):
        self.titulo: str = titulo
        self.fonte: str = fonte
        self.dados: list[list[str]] = dados if dados else []
        self.numero: int = 0
        self.estilo_borda: str = "abnt"
        self.centralizar_conteudo: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> Tabela:
        tabela = cls()
        for key, value in data.items():
            if hasattr(tabela, key):
                setattr(tabela, key, value)
        return tabela

    def to_dict(self) -> dict:
        """Converte a instância em um dicionário para salvar."""
        return self.__dict__

class Figura:
    """Armazena os dados de uma figura."""
    def __init__(self, titulo: str = "", fonte: str = ""):
        self.titulo: str = titulo
        self.fonte: str = fonte
        self.caminho_original: str = ""
        self.caminho_processado: str = ""
        self.largura_cm: float = 12.0
        self.numero: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> Figura:
        figura = cls()
        for key, value in data.items():
            if hasattr(figura, key):
                setattr(figura, key, value)
        return figura

    def to_dict(self) -> dict:
        """Converte a instância em um dicionário para salvar."""
        return self.__dict__

class Formula:
    """Armazena os dados de uma fórmula (LaTeX)."""
    
    def __init__(self, legenda: str = "", codigo_latex: str = ""):
        self.legenda: str = legenda 
        self.codigo_latex: str = codigo_latex
        self.caminho_svg: str = ""
        self.caminho_processado_png: str = ""
        self.largura_cm: float = 8.0
        self.numero: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> Formula:
        """Cria uma instância de Formula a partir de um dicionário."""
        formula = cls()
        for key, value in data.items():
            if hasattr(formula, key):
                setattr(formula, key, value)
        return formula
    
    # --- INÍCIO DA CORREÇÃO ---
    # Este método estava faltando
    def to_dict(self) -> dict:
        """Converte a instância em um dicionário para salvar."""
        return self.__dict__
    # --- FIM DA CORREÇÃO ---

# --- CLASSES DE LISTA ---

class ItemLista:
    """Representa um item individual em uma lista hierárquica."""
    def __init__(self, texto: str = "Novo Item"):
        self.texto: str = texto
        self.filhos: list[ItemLista] = []
        self.pai: ItemLista | None = None

    def adicionar_filho(self, filho: ItemLista):
        filho.pai = self
        self.filhos.append(filho)
    
    @classmethod
    def from_dict(cls, data: dict) -> ItemLista:
        item = cls(texto=data.get('texto', 'Item'))
        for filho_data in data.get('filhos', []):
            item.adicionar_filho(cls.from_dict(filho_data))
        return item
        
    def to_dict(self) -> dict:
        """Converte o item e seus filhos recursivamente em um dicionário."""
        return {
            "texto": self.texto,
            "filhos": [filho.to_dict() for filho in self.filhos]
        }


TipoEnumeracaoLista = Literal["Híbrida (ABNT)", "Numérica (Seção)", "Alfabética", "Símbolos"]

class ListaABNT:
    """Representa uma lista ABNT reutilizável e configurável."""
    def __init__(self, titulo: str = ""):
        self.titulo: str = titulo
        self.mostrar_titulo: bool = True
        self.tipo_enumeracao: TipoEnumeracaoLista = "Híbrida (ABNT)"
        self.numero: int = 0 
        self.raiz: ItemLista = ItemLista(texto="Raiz da Lista")

    @classmethod
    def from_dict(cls, data: dict) -> ListaABNT:
        lista = cls(titulo=data.get('titulo', 'Sem Título'))
        lista.mostrar_titulo = data.get('mostrar_titulo', True)
        lista.tipo_enumeracao = data.get('tipo_enumeracao', 'Híbrida (ABNT)')
        if 'raiz' in data and data['raiz']:
            lista.raiz = ItemLista.from_dict(data['raiz'])
        return lista

    def to_dict(self) -> dict:
        """Converte a lista e sua raiz recursivamente em um dicionário."""
        return {
            "titulo": self.titulo,
            "mostrar_titulo": self.mostrar_titulo,
            "tipo_enumeracao": self.tipo_enumeracao,
            "raiz": self.raiz.to_dict()
        }


class DocumentoABNT:
    """
    Classe principal que agrega todas as informações do documento ABNT.
    """
    def __init__(self):
        self.configuracoes: Configuracoes = Configuracoes()
        self.titulo: str = ""
        self.autores: list[Autor] = []
        self.orientador: str = ""
        self.resumo: str = ""
        self.palavras_chave: str = ""
        self.estrutura_textual: Capitulo = Capitulo(titulo="Raiz do Documento") 
        self.banco_tabelas: list[Tabela] = []
        self.banco_figuras: list[Figura] = []
        self.banco_formulas: list[Formula] = []
        self.banco_listas: list[ListaABNT] = []
        self.referencias: list = []

    def ordenar_referencias(self):
        """Ordena a lista de referências em ordem alfabética."""
        try:
            self.referencias.sort(key=lambda ref: ref.formatar_ordem().lower())
        except AttributeError:
            print("Aviso: Usando método de ordenação de fallback para referências.")
            self.referencias.sort(key=lambda ref: ref.autor.lower() if hasattr(ref, 'autor') else str(ref.__dict__))

    @classmethod
    def from_dict(cls, data: dict) -> DocumentoABNT:
        """
        Cria uma instância completa de DocumentoABNT a partir de um
        dicionário (lido de um arquivo de projeto).
        """
        doc = cls()
        doc.titulo = data.get('titulo', '')
        doc.orientador = data.get('orientador', '')
        doc.resumo = data.get('resumo', '')
        doc.palavras_chave = data.get('palavras_chave', '')

        if 'configuracoes' in data:
            doc.configuracoes = Configuracoes.from_dict(data['configuracoes'])
        
        doc.autores = [Autor.from_dict(d) for d in data.get('autores', [])]
        
        if 'estrutura_textual' in data:
            doc.estrutura_textual = Capitulo.from_dict(data['estrutura_textual'])
        
        doc.banco_tabelas = [Tabela.from_dict(d) for d in data.get('banco_tabelas', [])]
        doc.banco_figuras = [Figura.from_dict(d) for d in data.get('banco_figuras', [])]
        doc.banco_formulas = [Formula.from_dict(d) for d in data.get('banco_formulas', [])]
        doc.banco_listas = [ListaABNT.from_dict(d) for d in data.get('banco_listas', [])]
        
        doc.referencias = []
        try:
            from referencia import Livro, Artigo, Site
            for ref_data in data.get('referencias', []):
                ref_tipo = ref_data.get('ref_tipo') 
                
                if ref_tipo == 'Livro' and hasattr(Livro, 'from_dict'):
                    doc.referencias.append(Livro.from_dict(ref_data))
                elif ref_tipo == 'Artigo' and hasattr(Artigo, 'from_dict'):
                    doc.referencias.append(Artigo.from_dict(ref_data))
                elif ref_tipo == 'Site' and hasattr(Site, 'from_dict'):
                    doc.referencias.append(Site.from_dict(ref_data))
                else:
                    print(f"Aviso: Não foi possível carregar referência. Tipo desconhecido ou 'from_dict' ausente: {ref_tipo}")
        except ImportError:
            print("Aviso: Arquivo 'referencia.py' ou suas classes (Livro, Artigo, Site) não encontradas.")
        except Exception as e:
            print(f"Erro ao carregar referências: {e}")

        return doc

    def to_dict(self) -> dict:
        """
        Converte a instância completa do DocumentoABNT em um dicionário
        pronto para ser salvo como JSON.
        """
        
        referencias_serializadas = []
        try:
            from referencia import Livro, Artigo, Site
            
            for ref in self.referencias:
                if not hasattr(ref, 'to_dict'):
                    print(f"Aviso: Objeto de referência {type(ref)} não tem método to_dict(). Pulando.")
                    continue
                
                ref_data = ref.to_dict()
                
                if isinstance(ref, Livro):
                    ref_data['ref_tipo'] = 'Livro'
                elif isinstance(ref, Artigo):
                    ref_data['ref_tipo'] = 'Artigo'
                elif isinstance(ref, Site):
                    ref_data['ref_tipo'] = 'Site'
                else:
                    ref_data['ref_tipo'] = None
                
                referencias_serializadas.append(ref_data)
        
        except ImportError:
             print("Aviso: Não foi possível salvar referências. Classes 'Livro', 'Artigo' ou 'Site' não encontradas.")
        except Exception as e:
            print(f"Erro ao salvar referências: {e}")

        return {
            "configuracoes": self.configuracoes.to_dict(),
            "titulo": self.titulo,
            "autores": [autor.to_dict() for autor in self.autores],
            "orientador": self.orientador,
            "resumo": self.resumo,
            "palavras_chave": self.palavras_chave,
            "estrutura_textual": self.estrutura_textual.to_dict(),
            "banco_tabelas": [tabela.to_dict() for tabela in self.banco_tabelas],
            "banco_figuras": [figura.to_dict() for figura in self.banco_figuras],
            "banco_formulas": [formula.to_dict() for formula in self.banco_formulas],
            "banco_listas": [lista.to_dict() for lista in self.banco_listas],
            "referencias": referencias_serializadas
        }