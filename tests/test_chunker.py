from src.backend.app.utils.text import sliding_window


def test_sliding_window_overlap():
    text = "这是一个测试句子。" * 120
    chunks = list(sliding_window(text, size=120, overlap=20))
    assert len(chunks) > 1
    assert chunks[1][0] <= chunks[0][1]
    assert all(c[2] for c in chunks)
