from ballot import Ballot
from typing import Any
import discord
from election import Election
import math

STAR = "⭐"


class ScoreBallot(Ballot):
    def __init__(self, election: Election):
        super().__init__(election, "Rate each candidate from 0 to 5 stars.")
        self.ratings: dict[str, int] = {}

    def candidates_per_page(self) -> int:
        # Four rows; one select per row
        return 4

    def clear(self) -> None:
        self.ratings.clear()

    def get_items(
        self, candidates: list[str], session_id: int
    ) -> dict[discord.ui.Item]:
        class CandidateSelect(discord.ui.Select):
            def __init__(inner_self, candidate: str):
                super().__init__(
                    placeholder=f"{candidate}: {' '.join([STAR] * self.ratings.get(candidate, 0))}",
                    options=[
                        discord.SelectOption(
                            value=str(i),
                            label=f"{candidate}: {' '.join([STAR] * i)}",
                        )
                        for i in range(6)
                    ],
                )
                inner_self.candidate: str = candidate

            async def callback(inner_self, interaction: discord.Interaction):
                def modification():
                    self.ratings[inner_self.candidate] = int(inner_self.values[0])

                await self.modify(modification, interaction, session_id)

        return [CandidateSelect(c) for c in candidates]

    def submittable(self) -> bool:
        return bool(self.ratings)

    def to_markdown(self) -> str:
        lines = []
        for c in self.election.candidates:
            r = self.ratings.get(c, 0)
            stars = " ".join([STAR] * r) if r else "(zero stars)"
            lines.append(f"**{c}**:\n{stars}")
        return "\n\n".join(lines) if lines else "No ratings recorded"
