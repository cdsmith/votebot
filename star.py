from election import Election
from score_ballot import ScoreBallot


class STARElection(Election):
    def blank_ballot(self) -> ScoreBallot:
        return ScoreBallot(self)

    def get_winners(self) -> list[str]:
        total_scores = {c: 0 for c in self.candidates}
        for ballot in self.submitted_ballots.values():
            for cand, rating in ballot.ratings.items():
                if cand in total_scores:
                    total_scores[cand] += rating

        sorted_candidates = sorted(
            total_scores.items(), key=lambda x: x[1], reverse=True
        )
        if len(sorted_candidates) < 2:
            return [sorted_candidates[0][0]] if sorted_candidates else []

        top_two = sorted_candidates[:2]
        finalist_a, _ = top_two[0]
        finalist_b, _ = top_two[1]

        a_preferred = 0
        b_preferred = 0
        for ballot in self.submitted_ballots.values():
            a_score = ballot.ratings.get(finalist_a, 0)
            b_score = ballot.ratings.get(finalist_b, 0)
            if a_score > b_score:
                a_preferred += 1
            elif b_score > a_score:
                b_preferred += 1

        if a_preferred > b_preferred:
            return [finalist_a]
        elif b_preferred > a_preferred:
            return [finalist_b]
        else:
            return [finalist_a, finalist_b]

    def get_tabulation_details(self) -> str:
        num_ballots = len(self.submitted_ballots)
        if num_ballots == 0:
            return "No ballots were submitted."

        total_scores = {c: 0 for c in self.candidates}
        for ballot in self.submitted_ballots.values():
            for cand, rating in ballot.ratings.items():
                if cand in total_scores:
                    total_scores[cand] += rating

        lines = ["**Average Scores:**"]
        sorted_candidates = sorted(
            total_scores.items(), key=lambda x: x[1], reverse=True
        )
        for c, s in sorted_candidates:
            lines.append(f"- {c}: {s/num_ballots:.2f}")

        lines.append("")

        if len(sorted_candidates) == 0:
            return "No candidates present."
        elif len(sorted_candidates) == 1:
            return f"Only one candidate: **{sorted_candidates[0][0]}** wins by default."

        top_two = sorted_candidates[:2]
        finalist_a, _ = top_two[0]
        finalist_b, _ = top_two[1]

        lines.append("**Top Two Finalists:**")
        lines.append(
            f"- {finalist_a} with average score {total_scores[finalist_a] / num_ballots:.2f}"
        )
        lines.append(
            f"- {finalist_b} with average score {total_scores[finalist_b] / num_ballots:.2f}"
        )
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
        elif b_preferred > a_preferred:
            lines.append("")
            lines.append(f"**{finalist_b} wins the runoff.**")
        else:
            lines.append("")
            lines.append(f"It's a tie.")

        return "\n".join(lines)
