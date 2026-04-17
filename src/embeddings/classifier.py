from __future__ import annotations

import re
from enum import Enum


class ContentType(str, Enum):
    TEXT = "text"
    CODE = "code"
    MIXED = "mixed"

CODE_KEYWORDS = [
    "def ", "class ", "import ", "from ", "return ", "async def ",
    "function ", "const ", "let ", "var ", "export ", "require(",
    "if (", "for (", "while (", "switch (", "catch (", "throw ",
    "public ", "private ", "protected ", "static ", "void ",
    "func ", "package ", "struct ", "interface{", "go func",
    "fn ", "impl ", "pub ", "mod ", "use ",
    "SELECT ", "INSERT ", "UPDATE ", "DELETE ", "CREATE TABLE",
    "#include", "namespace ", "template<",
]

CODE_PATTERNS = re.compile(
    r"```|"
    r"\b\w+\.\w+\(|"
    r"[{}\[\]];?\s*$|"
    r"=>|->|::|"
    r"^\s{2,}(if|for|while|return|def|class)\b|"
    r"#\s*(ifdef|ifndef|define|include)|"
    r"//\s*\w|/\*",
    re.MULTILINE,
)

TEXT_SIGNALS = [
    ". ", "? ", "! ", ", and ", ", but ", ", or ",
    "the ", "this ", "that ", "these ", "those ",
    "is ", "are ", "was ", "were ", "been ",
    "should ", "would ", "could ", "might ",
    "prefer ", "always ", "never ", "usually ",
    "because ", "however ", "therefore ",
]


class ContentClassifier:
    def classify(self, content: str) -> ContentType:
        if not content or not content.strip():
            return ContentType.TEXT

        code_score = 0
        text_score = 0
        lower = content.lower()

        for kw in CODE_KEYWORDS:
            code_score += lower.count(kw.lower())

        code_score += len(CODE_PATTERNS.findall(content))

        for sig in TEXT_SIGNALS:
            text_score += lower.count(sig.lower())

        if "```" in content:
            code_score += 5

        lines = content.split("\n")
        indented = sum(1 for line in lines if line.startswith("    ") or line.startswith("\t"))
        if len(lines) > 3 and indented / len(lines) > 0.4:
            code_score += 3

        total = code_score + text_score
        if total == 0:
            return ContentType.TEXT

        code_ratio = code_score / total
        if code_ratio > 0.6:
            return ContentType.CODE
        elif code_ratio > 0.3:
            return ContentType.MIXED
        return ContentType.TEXT
