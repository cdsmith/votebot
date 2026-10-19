from election import Election
from i18n import N_, _, ngettext
from ballots.ranked import RankedBallot
import random
from collections import defaultdict
from ballot import Ballot
from typing import Iterable


class TidemanAlternativeElection(Election):
    @classmethod
    def method_name(self) -> str:
        return N_("Tideman's Alternative Method")

    def blank_ballot(self) -> RankedBallot:
        candidates = list(self.candidates)
        random.shuffle(candidates)
        return RankedBallot(self.election_id, candidates)

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

            lines.append(_("**Round {round}:**").format(round=round_num))
            lines.append(
                _("Candidates: {candidates}").format(
                    candidates=", ".join(sorted(active_candidates))
                )
            )
            lines.append(
                _("{active}; {exhausted}.").format(
                    active=ngettext(
                        "{n} active ballot", "{n} active ballots", total_ballots
                    ).format(n=total_ballots),
                    exhausted=ngettext(
                        "{n} exhausted ballot", "{n} exhausted ballots", total_exhausted
                    ).format(n=total_exhausted),
                )
            )

            if total_ballots == 0:
                # All ballots exhausted, all active candidates tie
                lines.append(_("All ballots are exhausted."))
                return list(active_candidates), "\n".join(lines)

            lines.append(_("First place votes:"))
            for c, v in sorted_candidates:
                lines.append(f"- {c}: {v} ({v / total_ballots:.2%})")

            majority = total_ballots / 2
            leader, leader_count = sorted_candidates[0]
            if leader_count > majority:
                lines.append(
                    _("Winner: **{candidate}** with a majority of active votes.").format(
                        candidate=leader
                    )
                )
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
                    # Ranked candidates are preferred over unranked ones.
                    for c in active_candidates.difference(ranking):
                        pairwise[ranking[i]][c] += 1
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
                lines.append(_("Eliminating all candidates not in the Smith set:"))
                lines.append(", ".join(sorted(active_candidates - smith_set)))

                active_candidates = smith_set
            else:
                min_votes = min(counts.values())
                to_eliminate = [c for c, v in counts.items() if v == min_votes]

                if len(to_eliminate) == 1:
                    loser = to_eliminate[0]
                    lines.append(
                        _("Eliminated {candidate} with fewest first-place votes.").format(
                            candidate=loser
                        )
                    )
                else:
                    lines.append(
                        _("Tie for fewest first-place votes: {candidates}").format(
                            candidates=", ".join(sorted(to_eliminate))
                        )
                    )
                    loser = random.choice(to_eliminate)
                    lines.append(
                        _("Eliminated: {candidate}, by random selection.").format(
                            candidate=loser
                        )
                    )

                active_candidates.remove(loser)

            round_num += 1
