from ballot import Ballot
from typing import Optional
import discord
from election import Election


class RankedBallot(Ballot):
    def __init__(self, election: Election):
        super().__init__(
            election,
            (
                "Select candidates in the order of your preference. "
                "You can submit at any time.  You need not rank all candidates."
            ),
        )
        self.ranking: list[str] = []

    def candidates_per_page(self) -> Optional[int]:
        # One page is enough
        return None

    def clear(self) -> None:
        self.ranking.clear()

    def get_items(
        self, candidates: list[str], session_id: int
    ) -> list[discord.ui.Item]:
        remaining_candidates = [
            c for c in candidates if c not in self.ranking
        ]

        class CandidateSelect(discord.ui.Select):
            def __init__(inner_self, candidates: list[str], partial: bool):
                place = len(self.ranking) + 1
                range = f" ({candidates[0]} - {candidates[-1]})" if partial else ""
                options = [
                    discord.SelectOption(label=c, description=f"Rank {c} as #{place}")
                    for c in candidates
                ]
                super().__init__(
                    placeholder=f"Select a candidate to rank #{place}...{range}",
                    options=options,
                )

            async def callback(inner_self, interaction: discord.Interaction):
                def modification():
                    self.ranking.append(inner_self.values[0])

                await self.modify(modification, interaction, session_id)

        options = []
        for i in range(0, len(remaining_candidates), 25):
            if remaining_candidates:
                partial = i > 0 or len(remaining_candidates) > 25
                options.append(
                    CandidateSelect(remaining_candidates[i : i + 25], partial)
                )
        return options

    def submittable(self) -> bool:
        return bool(self.ranking)

    def to_markdown(self) -> str:
        if self.ranking:
            desc_lines = [f"{i}. {c}" for i, c in enumerate(self.ranking, start=1)]
            return "\n".join(desc_lines)
        else:
            return "No candidates ranked."
