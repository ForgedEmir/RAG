"""Test de charge Oracle LoreKeeper — 20 utilisateurs simultanés.
Lancement : locust --headless -u 20 -r 2 --run-time 60s --host http://127.0.0.1:8000
"""
import random
from locust import HttpUser, task, between

# Questions variées basées sur les fichiers de lore réels
QUESTIONS = [
    "Qui est Lucas ?",
    "Qui est Ediz ?",
    "Quels sont les artefacts du jeu ?",
    "Quelles sont les factions principales ?",
    "Quels lieux existe-t-il dans le lore ?",
    "Qui sont les personnages principaux ?",
    "Raconte-moi un événement important du lore.",
    "Quels sont les PNJ connus ?",
    "Comment s'appelle le roi ?",
    "Qu'est-ce que le donjon ?",
    "Quels pouvoirs possède Ediz ?",
    "Quelle est l'histoire de Lucas ?",
    "Quelles factions s'affrontent ?",
    "Décris un lieu important du lore.",
    "Qui est Emir dans le lore ?",
]

# JWT de test — récupéré depuis les DevTools
TEST_JWT = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjIxYmUxOGYyLTAwNDUtNDY4Yi04NTcyLTc4Mzk4MGYyZjU5MCIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL3NzdHh6cG1vZ25nbHlidGh1Z3FmLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI1ZTUzNzc3NS05ZjFkLTQ3NGYtYjlmMy1mOGMxZmRhMDg1ZmMiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzc1NzYyMTY3LCJpYXQiOjE3NzU3NTg1NjcsImVtYWlsIjoiZW1pci5tYWtodHNhZXYucHJvQGdtYWlsLmNvbSIsInBob25lIjoiIiwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiZ2l0aHViIiwicHJvdmlkZXJzIjpbImdpdGh1YiJdfSwidXNlcl9tZXRhZGF0YSI6eyJhdmF0YXJfdXJsIjoiaHR0cHM6Ly9hdmF0YXJzLmdpdGh1YnVzZXJjb250ZW50LmNvbS91LzI0NDYwMDE3Nz92PTQiLCJlbWFpbCI6ImVtaXIubWFraHRzYWV2LnByb0BnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiZnVsbF9uYW1lIjoiRW1pciIsImlzcyI6Imh0dHBzOi8vYXBpLmdpdGh1Yi5jb20iLCJuYW1lIjoiRW1pciIsInBob25lX3ZlcmlmaWVkIjpmYWxzZSwicHJlZmVycmVkX3VzZXJuYW1lIjoiRm9yZ2VkRW1pciIsInByb3ZpZGVyX2lkIjoiMjQ0NjAwMTc3Iiwic3ViIjoiMjQ0NjAwMTc3IiwidXNlcl9uYW1lIjoiRm9yZ2VkRW1pciJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6Im9hdXRoIiwidGltZXN0YW1wIjoxNzc1NjQ0MzYyfV0sInNlc3Npb25faWQiOiJjNTgxMjRmZS0xYWZjLTQwMTAtODFlYy1iMGIyNWIzMmY5YjMiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.5ogGFAc_XpDaQGnE9L9mDbvFMyjfe_pL0_uIS7ZFqxs7vKB4q2rqEOF6jPnb8jyruiNozN-ZbpbXDeoz0iNJcg"


class LoreKeeperUser(HttpUser):
    wait_time = between(1, 4)  # délai réaliste entre les questions

    @task
    def ask_question(self):
        question = random.choice(QUESTIONS)
        with self.client.post(
            "/api/ask",
            json={"question": question, "session_id": ""},
            headers={"Authorization": f"Bearer {TEST_JWT}"},
            stream=True,
            catch_response=True,
            timeout=30,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(3)
    def health_check(self):
        self.client.get("/health")
