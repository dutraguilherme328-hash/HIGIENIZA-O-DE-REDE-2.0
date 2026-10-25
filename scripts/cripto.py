"""
Criptografia do site (AES-256-GCM + PBKDF2-SHA256), compatível com a Web Crypto API do navegador.

- Os dados do painel são cifrados com uma CHAVE DO SITE (32 bytes aleatórios) guardada em
  dados/.chave_site — fora do git. Sem ela não é possível atualizar o site.
- Cada usuário tem a chave do site "embrulhada" com uma chave derivada da senha dele
  (PBKDF2, 600 mil iterações). O site guarda só esse embrulho, nunca a senha.
- O nome do usuário vai como hash SHA-256, para não expor a lista de quem tem acesso.
"""
import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

RAIZ = Path(__file__).resolve().parent.parent
CHAVE = RAIZ / "dados" / ".chave_site"
ACESSO = RAIZ / "docs" / "acesso.js"
ITERACOES = 600_000

b64 = lambda b: base64.b64encode(b).decode()
unb64 = base64.b64decode


def chave_site(criar=False):
    if CHAVE.exists():
        return unb64(CHAVE.read_text().strip())
    if not criar:
        raise SystemExit(f"Chave do site não encontrada em {CHAVE}. Copie o arquivo .chave_site para a pasta dados.")
    CHAVE.parent.mkdir(parents=True, exist_ok=True)
    k = os.urandom(32)
    CHAVE.write_text(b64(k))
    return k


def cifrar(texto: str, chave: bytes) -> dict:
    iv = os.urandom(12)
    return {"iv": b64(iv), "ct": b64(AESGCM(chave).encrypt(iv, texto.encode("utf-8"), None))}


def id_usuario(usuario: str) -> str:
    return hashlib.sha256(usuario.strip().lower().encode("utf-8")).hexdigest()


def kek(senha: str, sal: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, ITERACOES, 32)


def ler_acesso() -> dict:
    if not ACESSO.exists():
        return {"versao": 1, "iteracoes": ITERACOES, "usuarios": {}}
    t = ACESSO.read_text(encoding="utf-8")
    return json.loads(t[t.index("{"): t.rindex("}") + 1])


def gravar_acesso(acesso: dict):
    ACESSO.write_text("window.ACESSO = " + json.dumps(acesso, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")


def embrulhar(senha: str, chave: bytes) -> dict:
    sal, iv = os.urandom(16), os.urandom(12)
    return {"sal": b64(sal), "iv": b64(iv), "chave": b64(AESGCM(kek(senha, sal)).encrypt(iv, chave, None))}


def confere(senha: str, registro: dict, chave: bytes) -> bool:
    try:
        return AESGCM(kek(senha, unb64(registro["sal"]))).decrypt(unb64(registro["iv"]), unb64(registro["chave"]), None) == chave
    except Exception:
        return False
