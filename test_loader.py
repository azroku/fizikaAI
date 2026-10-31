from rag.document_loader import load_docx


text = load_docx(
    "data/knowledge_base/1_razred/kinematika/"
    "kinematika_nastavni_materijal.docx"
)


print(text)