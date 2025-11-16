# referencia.py
# Descrição: Classes para modelar e formatar diferentes tipos de referências.

from dataclasses import dataclass

def formatar_autores(autores_str: str) -> str:
    if not autores_str:
        return ""
    autores = [a.strip() for a in autores_str.split(';')]
    autores_formatados = []
    for autor in autores:
        partes = autor.split()
        if len(partes) > 1:
            sobrenome = partes[-1].upper()
            prenomes = " ".join(partes[:-1])
            autores_formatados.append(f"{sobrenome}, {prenomes}")
        else:
            autores_formatados.append(autor.upper())
    return " ; ".join(autores_formatados)

class Referencia:
    def __init__(self, tipo: str, autores: str, titulo: str, ano: int):
        self.tipo = tipo
        self.autores = autores
        self.titulo = titulo
        self.ano = ano

    def get_chave_ordenacao(self) -> str:
        primeiro_autor = self.autores.split(';')[0].strip()
        if not primeiro_autor:
            return self.titulo.upper()
        partes = primeiro_autor.split()
        return partes[-1].upper() if partes else ""

    def formatar(self) -> str:
        raise NotImplementedError

@dataclass
class Livro(Referencia):
    local: str
    editora: str

    def __init__(self, autores, titulo, ano, local, editora):
        super().__init__("Livro", autores, titulo, ano)
        self.local = local
        self.editora = editora

    def formatar(self) -> str:
        autores_fmt = formatar_autores(self.autores)
        return f"{autores_fmt}. **{self.titulo}**. {self.local}: {self.editora}, {self.ano}."

@dataclass
class Artigo(Referencia):
    revista: str
    volume: str
    pagina_inicial: int
    pagina_final: int

    def __init__(self, autores, titulo, ano, revista, volume, pagina_inicial, pagina_final):
        super().__init__("Artigo", autores, titulo, ano)
        self.revista = revista
        self.volume = volume
        self.pagina_inicial = pagina_inicial
        self.pagina_final = pagina_final

    def formatar(self) -> str:
        autores_fmt = formatar_autores(self.autores)
        return (f"{autores_fmt}. {self.titulo}. **{self.revista}**, v. {self.volume}, "
                f"p. {self.pagina_inicial}-{self.pagina_final}, {self.ano}.")

@dataclass
class Site(Referencia):
    url: str
    data_acesso: str

    def __init__(self, autores, titulo, ano, url, data_acesso):
        super().__init__("Site", autores, titulo, ano)
        self.url = url
        self.data_acesso = data_acesso

    def formatar(self) -> str:
        autores_fmt = formatar_autores(self.autores)
        return (f"{autores_fmt}. {self.titulo}. {self.ano}. "
                f"Disponível em: <{self.url}>. Acesso em: {self.data_acesso}.")