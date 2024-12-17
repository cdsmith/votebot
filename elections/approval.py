from election import Election
from ballots.multichoice import MultiChoiceBallot


class ApprovalElection(Election):
    def blank_ballot(self) -> MultiChoiceBallot:
        return MultiChoiceBallot(self)

    def tabulate(self) -> tuple[list[str], str]:
        counts = {c: 0 for c in self.candidates}
        for ballot in self.submitted_ballots.values():
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