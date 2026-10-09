"""凭据保险库加解密。"""
from core.crypto import CredentialVault


def test_encrypt_decrypt_roundtrip():
    v = CredentialVault()
    token = v.encrypt("s3cr3t/汉字@123")
    assert token and token != "s3cr3t/汉字@123"
    assert v.decrypt(token) == "s3cr3t/汉字@123"


def test_none_and_empty():
    v = CredentialVault()
    assert v.encrypt(None) == ""
    assert v.decrypt("") == ""
    assert v.decrypt(v.encrypt("")) == ""
