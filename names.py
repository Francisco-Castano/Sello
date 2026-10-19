"""
Formato de nombres de personas.
Pone en mayúscula la primera letra de cada palabra: "felipe amelong" -> "Felipe Amelong".
"""

# Partículas que van en minúscula salvo al principio: "María de la Cruz"
LOWERCASE_PARTICLES = {"de", "del", "la", "las", "los", "y", "da", "do", "dos", "van", "von"}


def _capitalize_word(word: str) -> str:
    # Respeta guiones y apóstrofes: "ana-lía" -> "Ana-Lía", "o'connor" -> "O'Connor"
    for separator in ("-", "'"):
        if separator in word:
            return separator.join(_capitalize_word(part) for part in word.split(separator))
    return word[:1].upper() + word[1:].lower()


def format_person_name(name: str) -> str:
    words = name.split()
    return " ".join(
        word.lower() if i > 0 and word.lower() in LOWERCASE_PARTICLES else _capitalize_word(word)
        for i, word in enumerate(words)
    )
