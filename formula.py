# formula.py
from dataclasses import dataclass

@dataclass
class Formula:
    legenda: str = ""
    codigo_latex: str = r"\frac{-b \pm \sqrt{b^2-4ac}}{2a}"
    caminho_svg: str = ""
    caminho_processado_png: str = ""
    # NOVO: Adiciona controle de largura, com 16cm (largura máxima) como padrão.
    largura_cm: float = 16.0 
    numero: int = 0