from ballot import Ballot
from typing import Any
import discord
from election import Election


class RankedBallot(Ballot):
    def __init__(self, election: Election):
        self.election = election
        self.ranking: list[str] = []

    def copy(self) -> "RankedBallot":
        new_ballot = RankedBallot(self.election)
        new_ballot.ranking = self.ranking[:]
        return new_ballot

    def render_interim(self, session_id: int) -> dict[str, Any]:
        """Allow the user to add candidates to their ranking via a drop-down menu."""

        remaining_candidates = [
            c for c in self.election.candidates if c not in self.ranking
        ]

        embed = discord.Embed(
            title=self.election.title,
            description=(
                "Select candidates in the order of your preference. "
                "You can submit at any time.  You need not rank all candidates."
            ),
        )
        if self.ranking:
            desc_lines = [f"{i}. {c}" for i, c in enumerate(self.ranking, start=1)]
            embed.add_field(
                name="Current Ranking", value="\n".join(desc_lines), inline=False
            )
        else:
            embed.add_field(
                name="Current Ranking",
                value="*No candidates ranked yet.*",
                inline=False,
            )

        view = discord.ui.View()

        class CandidateSelect(discord.ui.Select):
            def __init__(inner_self, ballot: "RankedBallot", session_id: int):
                place = len(ballot.ranking) + 1
                options = [
                    discord.SelectOption(label=c, description=f"Rank {c} as #{place}")
                    for c in remaining_candidates
                ]
                super().__init__(
                    placeholder=f"Select a candidate to rank #{place}...",
                    options=options,
                )
                inner_self.ballot = ballot
                inner_self.session_id = session_id

            async def callback(inner_self, interaction: discord.Interaction):
                if not await inner_self.ballot.election.check_session(
                    interaction, inner_self.session_id
                ):
                    return
                chosen = inner_self.values[0]
                inner_self.ballot.ranking.append(chosen)
                await interaction.response.edit_message(
                    **inner_self.ballot.render_interim(inner_self.session_id)
                )

        class ResetButton(discord.ui.Button):
            def __init__(self, ballot: "RankedBallot", session_id: int):
                super().__init__(style=discord.ButtonStyle.danger, label="Start Over")
                self.ballot = ballot
                self.session_id = session_id

            async def callback(self, interaction: discord.Interaction):
                if await self.ballot.election.check_session(
                    interaction, self.session_id
                ):
                    self.ballot.ranking = []
                    await interaction.response.edit_message(
                        **self.ballot.render_interim(self.session_id)
                    )

        class SubmitButton(discord.ui.Button):
            def __init__(self, ballot: "RankedBallot", session_id: int):
                super().__init__(style=discord.ButtonStyle.green, label="Submit Vote")
                self.ballot = ballot
                self.session_id = session_id

            async def callback(self, interaction: discord.Interaction):
                if await self.ballot.election.check_session(
                    interaction, self.session_id
                ):
                    await self.ballot.election.submit_ballot(interaction)

        if remaining_candidates:
            view.add_item(CandidateSelect(self, session_id))
        view.add_item(ResetButton(self, session_id))
        if len(self.ranking) > 0:
            view.add_item(SubmitButton(self, session_id))

        return {
            "embed": embed,
            "view": view,
        }

    def render_submitted(self) -> dict[str, Any]:
        if self.ranking:
            desc_lines = [f"{i}. {c}" for i, c in enumerate(self.ranking, start=1)]
            ranking_str = "\n".join(desc_lines)
        else:
            ranking_str = "No candidates ranked."

        return {
            "content": "Your ranked vote has been submitted.",
            "embed": discord.Embed(title="Your Final Ranking").add_field(
                name="You ranked the candidates as:",
                value=ranking_str,
                inline=False,
            ),
        }
