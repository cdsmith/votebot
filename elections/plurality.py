from election import Election
from ballots.simple import SimpleBallot


class PluralityElection(Election):
    def name(self) -> str:
        return "Plurality"

    def blank_ballot(self) -> SimpleBallot:
        return SimpleBallot(self)

    def tabulate(self) -> tuple[list[str], str]:
        counts = {c: 0 for c in self.candidates}
        for ballot in self.submitted_ballots.values():
            if ballot.vote in counts:
                counts[ballot.vote] += 1
        sorted_candidates = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        if counts:
            max_score = max(counts.values())
            return [c for c, sc in counts.items() if sc == max_score], "\n".join(
                [f"**{c}:** {count}" for c, count in sorted_candidates]
            )
        else:
            return [], "No candidates were found."
