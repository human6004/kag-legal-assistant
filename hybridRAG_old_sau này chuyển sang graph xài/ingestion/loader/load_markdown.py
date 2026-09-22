from pathlib import Path
from llama_index.core import Document


class MarkdownLoader:

    def __init__(self, markdown_folder: str):
        self.markdown_folder = Path(markdown_folder)

    def load(self) -> list[Document]:

        documents = []

        for md_file in sorted(self.markdown_folder.rglob("*.md")):

            text = md_file.read_text(encoding="utf-8")

            documents.append(
                Document(
                    text=text,
                    metadata={ #de ko cho loader lam qua nhieu buoc nay
                        "source": md_file.name,
                        "file_name": md_file.stem,
                        "file_path": str(md_file),
                        "file_type": "markdown",
                        "language": "vi",
                        "knowledge_base": "legal"
                    } # phan tao keywords, node gi do thi de cho buoc metadata xu ly rieng
                )
            )

        return documents