from ballot import Ballot
import discord
from election import Election


class SimpleBallot(Ballot):
    """
    A ballot that allows a user to vote for candidates.
    Can allow multiple votes if `multiple_votes` is set to True.
    """

    def __init__(self, election: Election, multiple_votes: bool = False):
        super().__init__(
            election,
            (
                "Please select all candidates you approve of."
                if multiple_votes
                else "Please select a candidate."
            ),
        )
        self.multiple_votes: bool = multiple_votes
        self.votes: set[str] = set()

    def candidates_per_page(self) -> int:
        # Four rows of five buttons
        return 20

    def clear(self) -> None:
        self.votes.clear()

    def get_items(
        self, candidates: list[str], session_id: int
    ) -> list[discord.ui.Item]:
        class VoteButton(discord.ui.Button):
            def __init__(
                inner_self,
                candidate: str,
            ):
                super().__init__(
                    style=discord.ButtonStyle.primary
                    if candidate in self.votes
                    else discord.ButtonStyle.gray,
                    label=candidate,
                )
                inner_self.candidate: str = candidate

            async def callback(inner_self, interaction: discord.Interaction):
                def modification():
                    if inner_self.candidate in self.votes:
                        self.votes.remove(inner_self.candidate)
                    elif self.multiple_votes:
                        self.votes.add(inner_self.candidate)
                    else:
                        self.votes = {inner_self.candidate}

                await self.modify(modification, interaction, session_id)

        return [VoteButton(c) for c in candidates]

    def submittable(self) -> bool:
        return bool(self.votes)

    def to_markdown(self) -> str:
        return ",".join(self.votes) if self.votes else "No vote recorded"
