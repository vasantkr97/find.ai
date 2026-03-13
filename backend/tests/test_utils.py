from app.core.utils import chunk_text, format_duration, truncate


def test_chunk_text_overlap() -> None:
    text = "a" * 250
    chunks = chunk_text(text, 100, 20)
    assert len(chunks) == 3
    assert len(chunks[0]) == 100
    assert chunks[1].startswith(chunks[0][-20:])


def test_truncate() -> None:
    assert truncate("hello", 10) == "hello"
    assert truncate("hello world this is long", 10) == "hello w..."


def test_format_duration() -> None:
    assert format_duration(500) == "500ms"
    assert format_duration(3500) == "3.5s"
    assert format_duration(125000) == "2m 5s"

