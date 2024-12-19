from election import Election
from ballots.simple import SimpleBallot
from ballot import Ballot
from typing import Iterable


class ApprovalElection(Election):
    @classmethod
    def method_name(self) -> str:
        return "Approval"

    def blank_ballot(self) -> SimpleBallot:
        return SimpleBallot(self, multiple_votes=True)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        counts = {c: 0 for c in self.candidates}
        for ballot in ballots:
            for cand in ballot.votes:
                if cand in counts:
                    counts[cand] += 1
        if counts:
            sorted_candidates = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            max_score = max(counts.values())
            return [c for c, sc in counts.items() if sc == max_score], "\n".join(
                [f"**{c}:** {count}" for c, count in sorted_candidates]
            )
        else:
            return [], "No candidates were found."
