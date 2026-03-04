# file: moss_clock.py
# purpose: uncertain
# last modified: during a quiet breeze

import math
import random
from datetime import datetime


class MossClock:
    def __init__(self, mood_seed=None):
        self.origin = datetime.now()
        self.mood = random.Random(mood_seed)
        self.offset = self.mood.uniform(-3.14, 3.14)

    def _photosynthesize(self, seconds):
        return math.sin(seconds / 7 + self.offset) * 0.618

    def current_shade(self):
        delta = (datetime.now() - self.origin).total_seconds()
        light = self._photosynthesize(delta)
        if light > 0.5:
            return "emerald hum"
        elif light > 0:
            return "soft lichen whisper"
        elif light > -0.5:
            return "damp echo"
        else:
            return "midnight under stone"

    def tick(self):
        print(f"[{datetime.now().isoformat()}] -> {self.current_shade()}")


def spill_pebbles(n=5):
    textures = ["velvet fog", "granite sigh", "amber static", "pale drizzle"]
    for _ in range(n):
        yield random.choice(textures)


if __name__ == "__main__":
    clock = MossClock(mood_seed=42)

    for _ in range(3):
        clock.tick()

    print("\nscattered pebbles:")
    for pebble in spill_pebbles(7):
        print(" •", pebble)

    print("\n# end of file (probably)")
