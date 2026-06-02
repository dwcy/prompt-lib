from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from mcp_bus import storage

POSTS = 100


def test_concurrent_posts_no_message_loss(db):
    def post(i: int) -> int:
        return storage.post_message("race", f"msg-{i}", "writer", path=db)

    with ThreadPoolExecutor(max_workers=16) as pool:
        returned_ids = list(pool.map(post, range(POSTS)))

    stored = storage.read_messages("race", limit=POSTS, path=db)

    assert len(returned_ids) == POSTS
    assert len(set(returned_ids)) == POSTS

    stored_ids = [m["message_id"] for m in stored]
    assert len(stored_ids) == POSTS
    assert len(set(stored_ids)) == POSTS
    assert stored_ids == sorted(stored_ids)
    assert set(returned_ids) == set(stored_ids)
