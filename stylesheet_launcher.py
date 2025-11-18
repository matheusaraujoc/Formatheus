# stylesheet_launcher.py
# Descrição: Folha de estilo QSS MÍNIMA para o Launcher.
# Define apenas o botão primário para qdarktheme.

def get_style_sheet():
    """
    Retorna o QSS mínimo para o launcher.
    """
    return """
    
/* Botão de Ação Primária (Azul/Verde) */
QPushButton[cssClass="primary"] {
    /* qdarktheme irá aplicar as cores corretas de 
       background, color, e border-color automaticamente */
    font-weight: bold;
}

/* Botão Destrutivo (Vermelho) */
QPushButton[cssClass="destructive"] {
    background-color: #d13438;
    color: white; 
    border: 1px solid #d13438;
}
QPushButton[cssClass="destructive"]:hover {
    background-color: #a2282b;
    border: 1px solid #a2282b;
}
    
    """