import pytest

from src.embeddings.classifier import ContentClassifier, ContentType


@pytest.fixture
def classifier():
    return ContentClassifier()


class TestContentClassifier:
    def test_empty_content(self, classifier):
        assert classifier.classify("") == ContentType.TEXT
        assert classifier.classify("   ") == ContentType.TEXT

    def test_plain_text(self, classifier):
        content = "The user prefers dark mode and always uses vim keybindings."
        assert classifier.classify(content) == ContentType.TEXT

    def test_natural_language_preference(self, classifier):
        content = (
            "User is a senior backend engineer with 10 years of experience. "
            "They prefer functional programming patterns and should be given "
            "concise responses without excessive explanation."
        )
        assert classifier.classify(content) == ContentType.TEXT

    def test_code_snippet(self, classifier):
        content = """
def factorial(n):
    if n < 0:
        raise ValueError("negative")
    return 1 if n == 0 else n * factorial(n - 1)
"""
        assert classifier.classify(content) == ContentType.CODE

    def test_code_with_imports(self, classifier):
        content = """
import asyncio
from typing import Any

async def fetch_data(url: str) -> dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
"""
        assert classifier.classify(content) == ContentType.CODE

    def test_mixed_content(self, classifier):
        content = """
Always use dependency injection for services. Example:

```python
class UserService:
    def __init__(self, db: Database):
        self._db = db
```

This makes testing easier and follows the project conventions.
"""
        result = classifier.classify(content)
        assert result in (ContentType.CODE, ContentType.MIXED)

    def test_go_code(self, classifier):
        content = """
func main() {
    http.HandleFunc("/", handler)
    go func() {
        log.Fatal(http.ListenAndServe(":8080", nil))
    }()
}
"""
        assert classifier.classify(content) == ContentType.CODE

    def test_guideline_with_code_reference(self, classifier):
        content = "Prefer asyncio.gather() over sequential awaits for independent coroutines."
        result = classifier.classify(content)
        assert result in (ContentType.TEXT, ContentType.MIXED)

    def test_sql_code(self, classifier):
        content = """
SELECT u.id, u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2024-01-01'
GROUP BY u.id, u.name
"""
        assert classifier.classify(content) == ContentType.CODE
