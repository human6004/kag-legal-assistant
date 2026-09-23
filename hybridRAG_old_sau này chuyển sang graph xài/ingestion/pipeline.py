from ingestion.processes.clean_text import TextCleaner
from ingestion.processes.normalize import TextNormalizer


class IngestionPipeline:

    def __init__(self):

        self.cleaner = TextCleaner()
        self.normalizer = TextNormalizer()

    def run(self, documents):

        processed_documents = []

        for doc in documents:

            text = self.cleaner.clean(doc.text)
            text = self.normalizer.normalize(text)

            doc.text = text

            processed_documents.append(doc)

        return processed_documents