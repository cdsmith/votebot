from ballot import Ballot
import discord
import random

STAR = "⭐"
NONSTAR = "⚫"


def stars(n: int) -> str:
    return " ".join([STAR] * n + [NONSTAR] * (5 - n))


class ScoreBallot(Ballot):
    def __init__(
        self,
        election_id: int,
        candidates: list[str],
        ballot_id: int | None = None,
    ):
        super().__init__(
            election_id,
            candidates,
            "Rate each candidate from 0 to 5 stars.",
            ballot_id,
        )
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
                    placeholder=f"{candidate}: {stars(self.ratings.get(candidate, 0))}",
                    options=[
                        discord.SelectOption(
                            value=str(i),
                            label=f"{candidate}: {stars(i)}",
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
        for c in self.candidates:
            lines.append(f"**{c}**:\n{stars(self.ratings.get(c, 0))}")
        return "\n\n".join(lines) if lines else "No ratings recorded"

    def to_dict(self) -> dict:
        return {
            "ratings": self.ratings,
            "page": self.page,
            "visited_pages": list(self.visited_pages),
            "candidates": self.candidates,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, ballot_dict: dict, election_id: int) -> "ScoreBallot":
        data = ballot_dict["ballot_data"]

        ballot = cls(
            election_id=election_id,
            candidates=data["candidates"],
            ballot_id=ballot_dict["ballot_id"],
        )
        ballot.ratings = data["ratings"]
        ballot.page = data["page"]
        ballot.visited_pages = set(data["visited_pages"])
        ballot.session_id = ballot_dict["session_id"]

        return ballot
