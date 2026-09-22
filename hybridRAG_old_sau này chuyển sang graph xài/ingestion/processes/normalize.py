import unicodedata


class TextNormalizer:

    def normalize(self, text: str) -> str:

        text = unicodedata.normalize(
            "NFC",
            text
        )

        return text