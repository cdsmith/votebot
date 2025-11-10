from election import Election
from ballots.ranked import RankedBallot
from ballot import Ballot
from typing import Iterable
import random


class RankedPairsElection(Election):
    @classmethod
    def method_name(self) -> str:
        return "Ranked Pairs"

    def blank_ballot(self) -> RankedBallot:
        candidates = list(self.candidates)
        random.shuffle(candidates)
        return RankedBallot(self.election_id, candidates)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        pairwise = {
            (a, b): 0 for a in self.candidates for b in self.candidates if a != b
        }
        for ballot in ballots:
            for i, a in enumerate(ballot.ranking):
                for b in ballot.ranking[i + 1 :]:
                    pairwise[(a, b)] += 1
                unranked = set(self.candidates) - set(ballot.ranking)
                for b in unranked:
                    pairwise[(a, b)] += 1

        lines = []
        lines.append("**Pairwise Matchups:**")

        margins = {}
        for (a, b) in pairwise.keys():
            a_wins = pairwise[(a, b)]
            b_wins = pairwise[(b, a)]
            if a_wins > b_wins:
                if a < b:
                    lines.append(f"- {a} defeats {b}: {a_wins}-{b_wins}")
                margins[(a, b)] = a_wins - b_wins
            elif b_wins > a_wins:
                if a < b:
                    lines.append(f"- {b} defeats {a}: {b_wins}-{a_wins}")
                margins[(b, a)] = b_wins - a_wins
            else:
                if a < b:
                    lines.append(f"- {a} and {b} tie: {a_wins}-{b_wins}")

        lines.append("")
        lines.append("**Locked rankings:**")

        locked_pairs = []

        def reachable(x, y):
            visited = set()
            stack = [x]
            while stack:
                node = stack.pop()
                if node == y:
                    return True
                visited.add(node)
                stack.extend(
                    [
                        dest
                        for src, dest in locked_pairs
                        if src == node and dest not in visited
                    ]
                )

        for (a, b), _ in sorted(margins.items(), key=lambda x: x[1], reverse=True):
            if not reachable(b, a):
                lines.append(f"- {a} > {b}")
                locked_pairs.append((a, b))
            else:
                lines.append(
                    f"- Ignoring {a} > {b} because it contradicts stronger preferences"
                )

        beat_counts = {c: 0 for c in self.candidates}
        for _, b in locked_pairs:
            beat_counts[b] += 1

        lines.append("")
        lines.append("**Final ordering:**")

        last_score = None
        rank = 0
        winners = []
        for i, (c, score) in enumerate(sorted(beat_counts.items(), key=lambda x: x[1])):
            if score != last_score:
                rank = i + 1
            lines.append(f"{rank}. {c}")
            if rank == 1:
                winners.append(c)

        return winners, "\n".join(lines)
