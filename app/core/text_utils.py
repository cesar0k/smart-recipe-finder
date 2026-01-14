import re
from typing import Any, cast

import inflect
import pymorphy3

inflect_engine = inflect.engine()
morph = pymorphy3.MorphAnalyzer()


def is_cyrillic(text: str) -> bool:
    """
    Check if a string contains Cyrillic characters
    """
    return bool(re.search("[а-яА-Я]", text))


def get_word_forms(word: str) -> set[str]:
    """
    Smart word forms generation for search
    Supports English and Russian
    """
    clean_word = word.lower().strip()
    if not clean_word:
        return set()

    forms = {clean_word}

    if is_cyrillic(clean_word):
        parsed = morph.parse(clean_word)[0]

        normal_form = parsed.normal_form
        forms.add(normal_form)

        try:
            plural = parsed.inflect({"plur", "nomn"})
            if plural:
                forms.add(plural.word)
        except Exception:
            pass
    else:
        singular = inflect_engine.singular_noun(cast(Any, clean_word))
        if singular:
            forms.add(singular)

        plural = inflect_engine.plural(cast(Any, clean_word))
        if plural:
            forms.add(plural)

    return forms
