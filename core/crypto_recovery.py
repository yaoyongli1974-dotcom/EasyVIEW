"""启动期自愈：扫描 cameras 表，对加密密码尝试解密，失败则清空。

设计动机：
- 2026-09-01 真机报告：旧版 CredentialVault 在 keyring 写入失败时会重新生成新密钥
  并覆盖本地 fallback 文件，导致下次启动 key 变更、密文无法解密
  （cryptography.fernet.InvalidToken），app 启动崩溃。
- 本模块在 init_db() 末尾被调用，发现坏密文后把 password 置为空字符串，
  保留摄像机的名称/IP/通道/厂商等元数据，用户重新输入密码即可使用，
  不再导致崩溃。
"""
from cryptography.fernet import InvalidToken

from core.crypto import get_vault
from core.database import get_conn


def recover_invalid_credentials() -> int:
    """扫描 cameras 表，逐行尝试解密 password；InvalidToken 则把 password 置空。

    返回：被修复（清空 password）的行数。
    """
    vault = get_vault()
    conn = get_conn()
    rows = conn.execute("SELECT id, name, password FROM cameras WHERE password != ''").fetchall()
    bad_ids: list[int] = []
    bad_names: list[str] = []
    for r in rows:
        try:
            vault.decrypt(r["password"])
        except InvalidToken:
            bad_ids.append(r["id"])
            bad_names.append(r["name"])
        except Exception:
            # 其他异常（如非 base64）也当作损坏处理
            bad_ids.append(r["id"])
            bad_names.append(r["name"])

    if bad_ids:
        # 修复：将这些行的 password 字段置空（保留其他字段）
        placeholders = ",".join("?" * len(bad_ids))
        conn.execute(
            f"UPDATE cameras SET password = '' WHERE id IN ({placeholders})",
            bad_ids,
        )
        conn.commit()
    conn.close()
    if bad_names:
        print(f"[crypto_recovery] 已清空 {len(bad_names)} 条摄像机密码（密钥变更导致密文不可解密）：{bad_names}")
    return len(bad_ids)