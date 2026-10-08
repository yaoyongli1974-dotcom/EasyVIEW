"""回放检索：录像片段索引（SQLite）与查询。"""
import os
import time

from core.database import get_conn


def add_recording(camera_id: int, path: str, start: float, end: float,
                 trigger: str = "manual", plan_id: int = 0) -> int:
    """写入一段录像元数据。trigger: manual / schedule / motion。"""
    conn = get_conn()
    size = os.path.getsize(path) if os.path.exists(path) else 0
    cur = conn.execute(
        "INSERT INTO recordings (camera_id, path, start_time, end_time, size, trigger, plan_id) "
        "VALUES (?,?,?,?,?,?,?)",
        (camera_id, path, start, end, size, trigger, plan_id),
    )
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def search_recordings(camera_id: int = None, date: str = None) -> list[dict]:
    """检索录像片段。

    date: 'YYYY-MM-DD' 可选，按天过滤。
    """
    conn = get_conn()
    if camera_id is not None:
        rows = conn.execute(
            "SELECT * FROM recordings WHERE camera_id=? ORDER BY start_time DESC",
            (camera_id,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM recordings ORDER BY start_time DESC").fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    if date:
        result = [r for r in result if time.strftime("%Y-%m-%d", time.localtime(r["start_time"])) == date]
    return result


def delete_recording(rid: int) -> None:
    conn = get_conn()
    row = conn.execute("SELECT path FROM recordings WHERE id=?", (rid,)).fetchone()
    if row and os.path.exists(row["path"]):
        try:
            os.remove(row["path"])
        except OSError:
            pass
    conn.execute("DELETE FROM recordings WHERE id=?", (rid,))
    conn.commit()
    conn.close()
