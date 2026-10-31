from rag.retriever import PhysicsRetriever


retriever = PhysicsRetriever(
    "data/knowledge_base/1_razred/kinematika"
)


question = "Šta je ubrzanje?"
question = "Šta je referentni sistem?"
question = "Šta znači ravnomjerno pravolinijsko kretanje?"
question = "Zašto mjerenje ponavljamo više puta?"


results = retriever.search(
    question,
    top_k=3
)


print("\nPITANJE:")
print(question)


for i, result in enumerate(results):

    print("\n================================")
    print(f"REZULTAT {i + 1}")
    print("================================")

    print("Similarity:", round(result["score"], 3))
    print("Source:", result["source"])

    print("\n", result["text"])