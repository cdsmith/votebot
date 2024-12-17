from election import Election
from simple_ballot import SimpleBallot


class PluralityElection(Election):
    def blank_ballot(self) -> SimpleBallot:
        return SimpleBallot(self)

    def get_winners(self) -> list[str]:
        counts = {c: 0 for c in self.candidates}
        for ballot in self.submitted_ballots.values():
            if ballot.vote in counts:
                counts[ballot.vote] += 1
        if counts:
            max_score = max(counts.values())
            return [c for c, sc in counts.items() if sc == max_score]
        else:
            return []

    def get_tabulation_details(self) -> str:
        counts = {c: 0 for c in self.candidates}
        for ballot in self.submitted_ballots.values():
            if ballot.vote in counts:
                counts[ballot.vote] += 1
        sorted_candidates = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return "\n".join([f"**{c}:** {count}" for c, count in sorted_candidates])
