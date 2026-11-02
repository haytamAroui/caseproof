"""Canonical, literal page labels. No implicit Roman-to-Arabic conversion or offsets."""

# Numeric labels and canonical Roman numerals (1-3999) in a single case only.
# The exact supplied text, including case or leading zeroes, is the identifier.
_ROMAN_LOWER = r"m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
_ROMAN_UPPER = r"M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
PAGE_LABEL_PATTERN = rf"^(?:[0-9]{{1,6}}|{_ROMAN_LOWER}|{_ROMAN_UPPER})$"
