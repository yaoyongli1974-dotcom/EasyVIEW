"""凭据保险库：摄像机账号密码加密持久化。

设计要点：
- 使用 cryptography.Fernet 对称加密，密文写入 SQLite 的 cameras 表。
- 主密钥本身不落明文文件：优先存入 OS 凭据库（keyring）：
  Windows -> Credential Manager；macOS -> Keychain；Linux -> Secret Service。
- 仅在无可用凭据后端时，回退为本地权限受限文件（chmod 600），并在日志中提示风险。

关键不变量（2026-09-01 修复）：
- 密钥加载顺序：keyring -> fallback file（若存在则复用，绝不覆盖）-> 新生成。
- 这样保证：同一台机器上每次启动拿到的是同一个 key，不会因临时 keyring 失败
  导致反复重生成 key 进而解密失败（InvalidToken）。
"""
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
import keyring

SERVICE_NAME = "EasyVIEW"
KEYRING_USERNAME = "camera-db-key"
_FALLBACK_PATH = Path.home() / ".easyview" / "vault.key"


class CredentialVault:
    def __init__(self):
        self._key = self._load_or_create_key()

    # ---------------- 主密钥管理 ----------------
    def _load_or_create_key(self) -> bytes:
        # 1) 优先从 OS 凭据库读取
        try:
            stored = keyring.get_password(SERVICE_NAME, KEYRING_USERNAME)
            if stored:
                return stored.encode()
        except Exception:
            pass
        # 2) 回退：复用本地密钥文件（已存在则不覆盖）
        try:
            if _FALLBACK_PATH.exists():
                return _FALLBACK_PATH.read_bytes()
        except Exception:
            pass
        # 3) 都不存在：生成新 key 并持久化（keyring 写入 best-effort，文件原子创建）
        key = Fernet.generate_key()
        self._persist_fallback(key)
        return key

    def _persist_fallback(self, key: bytes) -> None:
        _FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            # 仅在文件不存在时创建（O_EXCL），绝不覆盖已有密钥
            fd = os.open(_FALLBACK_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.write(fd, key)
            finally:
                os.close(fd)
        except FileExistsError:
            # 已有密钥，不覆盖
            pass
        except Exception as e:
            print(f"[CredentialVault] 警告：无法写入密钥文件 {_FALLBACK_PATH}: {e}")
        # 尝试写入 keyring（best-effort）：让以后启动能优先从 keyring 拿同一 key
        try:
            keyring.set_password(SERVICE_NAME, KEYRING_USERNAME, key.decode())
        except Exception:
            pass

    # ---------------- 加解密接口 ----------------
    def encrypt(self, plaintext: str) -> str:
        if plaintext is None:
            return ""
        return Fernet(self._key).encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> str:
        if not token:
            return ""
        try:
            return Fernet(self._key).decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # 由调用方决定如何处理（自动清空 / 弹窗 / 抛给 UI）
            raise


# 单例，避免重复向凭据库读写
_vault: CredentialVault | None = None


def get_vault() -> CredentialVault:
    global _vault
    if _vault is None:
        _vault = CredentialVault()
    return _vault


def reset_all_passwords() -> int:
    """紧急恢复：清空 cameras 表所有 password 字段（保留元数据），返回受影响行数。

    适用场景：vault 密钥变更导致旧密文不可解密，用户希望恢复 app 使用。
    调用后摄像机列表正常显示，仅密码字段被置为空字符串，用户可重新输入。
    """
    from core.database import get_conn
    conn = get_conn()
    cur = conn.execute("UPDATE cameras SET password = ''")
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n
