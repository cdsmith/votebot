from election import Election
from ballots.ranked import RankedBallot
from typing import Iterable
from ballot import Ballot

class BordaElection(Election):
    def name(self) -> str:
        return "Borda Count"

    def blank_ballot(self) -> RankedBallot:
        return RankedBallot(self)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        lines = []
        candidates = self.candidates
        num_candidates = len(candidates)

        scores = {c: 0 for c in candidates}
        for ballot in ballots:
            for i, candidate in enumerate(ballot.ranking):
                scores[candidate] += (num_candidates - 1 - i)

        sorted_candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        if len(sorted_candidates) == 0:
            lines.append("No ballots cast.")
            return [], "\n".join(lines)

        for c, s in sorted_candidates:
            lines.append(f"- {c}: {s}")

        top_score = sorted_candidates[0][1]
        winners = [c for c, s in sorted_candidates if s == top_score]

        return winners, "\n".join(lines)
