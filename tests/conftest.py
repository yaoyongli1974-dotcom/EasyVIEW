"""测试夹具：offscreen QApplication 与隔离的临时数据库。"""
import pytest


@pytest.fixture(scope="session")
def qt_app():
    pytest.importorskip("PyQt6")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """把 database 模块的 DB_PATH 指向临时文件，避免污染真实数据目录。"""
    import core.database as db

    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return db
