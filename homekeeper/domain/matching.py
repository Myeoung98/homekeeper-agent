import re


def match_repairmen(description: str, repairmen) -> list:
    def _tokenize(text: str) -> set:
        return set(re.sub(r'[^\w\s]', '', text.lower()).split())

    desc_words = _tokenize(description)
    return [r for r in repairmen if desc_words & _tokenize(r["service_type"])]
