from app.services.llm_service import ask_ollama

answer = ask_ollama("Explain TaskFlow in one sentence.")

print(answer)
