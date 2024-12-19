from election import Election
from ballots.ranked import RankedBallot
import random
from collections import defaultdict
from ballot import Ballot
from typing import Iterable


class TidemanAlternativeElection(Election):
    def name(self) -> str:
        return "Tideman's Alternative Method"

    def blank_ballot(self) -> RankedBallot:
        return RankedBallot(self)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        lines = []
        active_candidates = set(self.candidates)
        round_num = 1

        while True:
            counts = {c: 0 for c in active_candidates}
            total_ballots = 0
            total_exhausted = 0

            # Count first-place votes for active candidates
            for ballot in ballots:
                active = [c for c in ballot.ranking if c in active_candidates]
                if active:
                    counts[active[0]] += 1
                    total_ballots += 1
                else:
                    total_exhausted += 1

            sorted_candidates = sorted(counts.items(), key=lambda x: x[1], reverse=True)

            lines.append(f"**Round {round_num}:**")
            lines.append(f"Candidates: {', '.join(sorted(active_candidates))}")
            lines.append(
                f"{total_ballots} active ballots; {total_exhausted} exhausted ballots."
            )

            if total_ballots == 0:
                # All ballots exhausted, all active candidates tie
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

            # Compute the Smith set
            pairwise = {
                a: {b: 0 for b in active_candidates if b != a}
                for a in active_candidates
            }
            for ballot in ballots:
                ranking = [c for c in ballot.ranking if c in active_candidates]
                for i in range(len(ranking)):
                    for j in range(i + 1, len(ranking)):
                        pairwise[ranking[i]][ranking[j]] += 1
            smith_set = active_candidates
            losses = defaultdict(set)
            for a in active_candidates:
                for b in active_candidates:
                    if a != b and pairwise[a][b] <= pairwise[b][a]:
                        losses[a].add(b)

            def find_closure(c, visited=None):
                visited = visited or set()
                if c in visited:
                    return visited
                visited.add(c)
                for a in losses.get(c, []):
                    find_closure(a, visited)
                return visited

            for c in active_candidates:
                if c in smith_set:
                    closure = find_closure(c)
                    if len(closure) < len(smith_set):
                        smith_set = closure

            if len(smith_set) < len(active_candidates):
                lines.append("Eliminating all candidates not in the Smith set:")
                lines.append(", ".join(sorted(active_candidates - smith_set)))

                active_candidates = smith_set
            else:
                min_votes = min(counts.values())
                to_eliminate = [c for c, v in counts.items() if v == min_votes]

                if len(to_eliminate) == 1:
                    loser = to_eliminate[0]
                    lines.append(f"Eliminated {loser} with fewest first-place votes.")
                else:
                    lines.append(
                        f"Tie for fewest first-place votes: {', '.join(sorted(to_eliminate))}"
                    )
                    loser = random.choice(to_eliminate)
                    lines.append(f"Eliminated: {loser}, by random selection.")

                active_candidates.remove(loser)

            round_num += 1
