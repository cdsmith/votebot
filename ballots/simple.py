from ballot import Ballot
import discord
import random


class SimpleBallot(Ballot):
    """
    A ballot that allows a user to vote for candidates.
    Can allow multiple votes if `multiple_votes` is set to True.
    """

    def __init__(
        self,
        election_id: int,
        candidates: list[str],
        multiple_votes: bool = False,
        ballot_id: int | None = None,
    ):
        super().__init__(
            election_id,
            candidates,
            (
                "Please select all candidates you approve of."
                if multiple_votes
                else "Please select a candidate."
            ),
            ballot_id,
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
        return ", ".join(self.votes) if self.votes else "No vote recorded"

    def to_dict(self) -> dict:
        return {
            "votes": list(self.votes),
            "multiple_votes": self.multiple_votes,
            "page": self.page,
            "visited_pages": list(self.visited_pages),
            "candidates": self.candidates,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, ballot_dict: dict, election_id: int) -> "SimpleBallot":
        data = ballot_dict["ballot_data"]

        ballot = cls(
            election_id=election_id,
            candidates=data["candidates"],
            multiple_votes=data["multiple_votes"],
            ballot_id=ballot_dict["ballot_id"],
        )
        ballot.votes = set(data["votes"])
        ballot.page = data["page"]
        ballot.visited_pages = set(data["visited_pages"])
        ballot.session_id = ballot_dict["session_id"]

        return ballot
