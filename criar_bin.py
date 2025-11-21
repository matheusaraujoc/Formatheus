import zipfile
import os

# Configurações
PASTA_ORIGEM = os.path.join("build_main", "main_app.dist")
NOME_ARQUIVO_SAIDA = "app_core.bin"

def empacotar():
    if not os.path.exists(PASTA_ORIGEM):
        print(f"ERRO: A pasta '{PASTA_ORIGEM}' não existe.")
        return

    print(f"Criando pacote '{NOME_ARQUIVO_SAIDA}'...")
    
    # Remove anterior se existir
    if os.path.exists(NOME_ARQUIVO_SAIDA):
        os.remove(NOME_ARQUIVO_SAIDA)

    with zipfile.ZipFile(NOME_ARQUIVO_SAIDA, 'w', zipfile.ZIP_DEFLATED) as zipf:
        count = 0
        for root, dirs, files in os.walk(PASTA_ORIGEM):
            for file in files:
                caminho_completo = os.path.join(root, file)
                # Importante: Calcula o caminho relativo para que o exe fique na raiz do zip
                caminho_relativo = os.path.relpath(caminho_completo, PASTA_ORIGEM)
                zipf.write(caminho_completo, arcname=caminho_relativo)
                count += 1
        
        tamanho = os.path.getsize(NOME_ARQUIVO_SAIDA) / (1024*1024)
        print(f"SUCESSO! {count} arquivos compactados.")
        print(f"Arquivo gerado: {NOME_ARQUIVO_SAIDA} ({tamanho:.2f} MB)")

if __name__ == "__main__":
    empacotar()