from election import Election
from ballots.score import ScoreBallot


class STARElection(Election):
    def blank_ballot(self) -> ScoreBallot:
        return ScoreBallot(self)

    def tabulate(self) -> tuple[list[str], str]:
        if not self.submitted_ballots:
            return [], "No ballots were submitted."
        scores = {c: 0 for c in self.candidates}
        for ballot in self.submitted_ballots.values():
            for cand, rating in ballot.ratings.items():
                if cand in scores:
                    scores[cand] += rating
        scores = {c: s / len(self.submitted_ballots) for c, s in scores.items()}
        sorted_candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        lines = ["**Average Scores:**"]
        for c, s in sorted_candidates:
            lines.append(f"- {c}: {s:.2f}")

        lines.append("")

        if len(sorted_candidates) == 0:
            return [], "No candidates were found."
        elif len(sorted_candidates) == 1:
            return [
                sorted_candidates[0][0]
            ], f"Only one candidate: **{sorted_candidates[0][0]}** wins by default."

        top_two = sorted_candidates[:2]
        finalist_a, _ = top_two[0]
        finalist_b, _ = top_two[1]

        lines.append("**Top Two Finalists:**")
        lines.append(f"- {finalist_a} with average score {scores[finalist_a]:.2f}")
        lines.append(f"- {finalist_b} with average score {scores[finalist_b]:.2f}")
        lines.append("")

        a_preferred = 0
        b_preferred = 0
        for ballot in self.submitted_ballots.values():
            a_score = ballot.ratings.get(finalist_a, 0)
            b_score = ballot.ratings.get(finalist_b, 0)
            if a_score > b_score:
                a_preferred += 1
            elif b_score > a_score:
                b_preferred += 1

        lines.append("**Runoff:**")
        lines.append(f"- {finalist_a}: preferred by {a_preferred} ballots")
        lines.append(f"- {finalist_b}: preferred by {b_preferred} ballots")

        if a_preferred > b_preferred:
            lines.append("")
            lines.append(f"**{finalist_a} wins the runoff.**")
            winners = [finalist_a]
        elif b_preferred > a_preferred:
            lines.append("")
            lines.append(f"**{finalist_b} wins the runoff.**")
            winners = [finalist_b]
        else:
            lines.append("")
            lines.append(f"It's a tie.")
            winners = [finalist_a, finalist_b]

        return winners, "\n".join(lines)
