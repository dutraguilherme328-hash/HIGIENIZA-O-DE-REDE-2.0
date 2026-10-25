"""
Gerencia quem pode entrar no painel.

    python scripts\\usuarios.py adicionar guilherme            (pede a senha)
    python scripts\\usuarios.py adicionar maria --gerar        (gera uma senha forte e mostra uma vez)
    python scripts\\usuarios.py trocar guilherme               (troca a senha)
    python scripts\\usuarios.py remover maria
    python scripts\\usuarios.py listar                         (mostra quantos usuários há)

Depois de qualquer mudança, publique: git add docs\\acesso.js, git commit, git push
(ou rode atualizar_site.bat).

Remover um usuário impede novos logins com a senha dele. Para garantir que ninguém com uma
cópia antiga do site consiga ler os dados, use também:  python scripts\\usuarios.py nova-chave
(gera nova chave do site; todos os usuários precisam ser recadastrados).
"""
import argparse
import getpass
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cripto  # noqa: E402

MINIMO = 10


def gerar_senha(n=14):
    alfabeto = string.ascii_letters + string.digits
    while True:
        s = "".join(secrets.choice(alfabeto) for _ in range(n))
        if any(c.isdigit() for c in s) and any(c.isupper() for c in s) and any(c.islower() for c in s):
            return s


def pedir_senha():
    s = getpass.getpass(f"Senha (mínimo {MINIMO} caracteres): ")
    if len(s) < MINIMO:
        raise SystemExit("Senha curta demais.")
    if s != getpass.getpass("Confirme a senha: "):
        raise SystemExit("As senhas não conferem.")
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("acao", choices=["adicionar", "trocar", "remover", "listar", "nova-chave"])
    ap.add_argument("usuario", nargs="?")
    ap.add_argument("--gerar", action="store_true", help="gera uma senha forte automaticamente")
    ap.add_argument("--senha", help=argparse.SUPPRESS)  # uso em automação
    a = ap.parse_args()

    acesso = cripto.ler_acesso()
    if a.acao == "listar":
        print(f"{len(acesso['usuarios'])} usuário(s) com acesso. (Os nomes ficam guardados só como hash.)")
        return
    if a.acao == "nova-chave":
        if cripto.CHAVE.exists():
            cripto.CHAVE.unlink()
        cripto.chave_site(criar=True)
        cripto.gravar_acesso({"versao": 1, "iteracoes": cripto.ITERACOES, "usuarios": {}})
        print("Nova chave criada e todos os acessos apagados. Recadastre os usuários e rode atualizar_site.bat.")
        return
    if not a.usuario:
        raise SystemExit("Informe o usuário.")
    uid = cripto.id_usuario(a.usuario)
    if a.acao == "remover":
        if acesso["usuarios"].pop(uid, None) is None:
            raise SystemExit("Usuário não encontrado.")
        cripto.gravar_acesso(acesso)
        print(f"Usuário '{a.usuario}' removido. Publique a mudança.")
        return
    if a.acao == "adicionar" and uid in acesso["usuarios"]:
        raise SystemExit("Usuário já existe. Use 'trocar' para mudar a senha.")
    if a.acao == "trocar" and uid not in acesso["usuarios"]:
        raise SystemExit("Usuário não encontrado.")
    senha = a.senha or (gerar_senha() if a.gerar else pedir_senha())
    chave = cripto.chave_site(criar=True)
    acesso["usuarios"][uid] = cripto.embrulhar(senha, chave)
    cripto.gravar_acesso(acesso)
    print(f"Usuário '{a.usuario.strip().lower()}' {'cadastrado' if a.acao == 'adicionar' else 'atualizado'}.")
    if a.gerar:
        print(f"Senha gerada (anote agora, ela não fica salva): {senha}")


if __name__ == "__main__":
    main()
