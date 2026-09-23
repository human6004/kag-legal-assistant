import re


class TextCleaner:

    def clean(self, text: str) -> str:

        text = text.replace("\ufeff", "")

        # doi may cai tab thanh space
        text = text.replace("\t", " ")

        # bo khoang trang cuoi dong
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)

        # neu ma nhieu dong trong thi de thanh 2 dong thoi
        text = re.sub(r"\n{3,}", "\n\n", text)

        # nhiều space liên tiếp
        text = re.sub(r" {2,}", " ", text)

        return text.strip()