"""Test de charge Oracle LoreKeeper — 20 utilisateurs simultanés.
Lancement : locust --headless -u 20 -r 2 --run-time 60s --host http://127.0.0.1:8000
"""
import os
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

# Prefer a short-lived bearer token from env.
# If not provided, use guest mode header (requires ALLOW_GUEST_MODE=true).
TEST_JWT = os.getenv("LOCUST_BEARER_TOKEN", "").strip()
TEST_GUEST_ID = os.getenv("LOCUST_GUEST_ID", "guest_locust_test")


class LoreKeeperUser(HttpUser):
    wait_time = between(1, 4)  # délai réaliste entre les questions

    def _auth_headers(self):
        if TEST_JWT:
            return {"Authorization": f"Bearer {TEST_JWT}"}
        return {"x-local-guest-id": TEST_GUEST_ID}

    @task
    def ask_question(self):
        question = random.choice(QUESTIONS)
        with self.client.post(
            "/api/ask",
            json={"question": question, "session_id": ""},
            headers=self._auth_headers(),
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
