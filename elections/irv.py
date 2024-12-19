from election import Election
from ballots.ranked import RankedBallot
import random
from ballot import Ballot
from typing import Iterable


class IRVElection(Election):
    def name(self) -> str:
        return "Instant Runoff"

    def blank_ballot(self) -> RankedBallot:
        return RankedBallot(self)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        lines = []
        active_candidates = set(self.candidates)
        round = 1

        while True:
            counts = {c: 0 for c in active_candidates}
            total_ballots = 0
            total_exhausted = 0

            for ballot in ballots:
                active = [c for c in ballot.ranking if c in active_candidates]
                if active:
                    counts[active[0]] += 1
                    total_ballots += 1
                else:
                    total_exhausted += 1

            sorted_candidates = sorted(counts.items(), key=lambda x: x[1], reverse=True)

            lines.append(f"**Round {round}:**")
            lines.append(f"Candidates: {', '.join(sorted(active_candidates))}")
            lines.append(
                f"{total_ballots} active ballots; {total_exhausted} exhausted ballots."
            )

            if total_ballots == 0:
                lines.append("All ballots are exhausted.")
                return list(active_candidates), "\n".join(lines)

            lines.append("First place votes:")
            for c, v in sorted_candidates:
                lines.append(f"- {c}: {v} ({v / total_ballots:.2%})")

            majority = total_ballots / 2
            leader, leader_count = sorted_candidates[0]

            if leader_count > majority:
                lines.append(f"Winner: **{leader}** with a majority of active votes.")
                return [leader], "\n".join(lines)

            min_votes = min(counts.values()) if counts else 0
            to_eliminate = [c for c, v in counts.items() if v == min_votes]

            if len(to_eliminate) == 1:
                loser = to_eliminate[0]
                lines.append(f"Eliminated: {loser}")
            else:
                lines.append(
                    f"Tie for fewest first-place votes: {', '.join(sorted(to_eliminate))}"
                )
                loser = random.choice(to_eliminate)
                lines.append(f"Eliminated: {loser}, by random selection.")

            active_candidates.remove(loser)
            round += 1
