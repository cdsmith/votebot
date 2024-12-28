import random
from fractions import Fraction
from typing import Iterable
from election import Election
from ballots.ranked import RankedBallot
from ballot import Ballot

NUMBER_OF_WINNERS = "Number of Winners"


class STVElection(Election):
    @classmethod
    def method_name(cls) -> str:
        return "Single Transferable Vote / Instant Runoff"

    @classmethod
    def method_description(cls, method_params: dict[str, str]) -> str:
        if method_params[NUMBER_OF_WINNERS] == "1":
            return "Instant Runoff"
        else:
            return (
                f"Single Transferable Vote for {method_params[NUMBER_OF_WINNERS]} seats"
            )

    @classmethod
    def method_param_names(cls) -> list[str]:
        return [NUMBER_OF_WINNERS]

    @classmethod
    def default_method_params(self):
        return {NUMBER_OF_WINNERS: "1"}

    @classmethod
    def validate_method_params(
        cls, params: dict[str, str], candidates: list[str]
    ) -> str | None:
        winners_str = params.get(NUMBER_OF_WINNERS, "1")
        try:
            n = int(winners_str)
            if n < 1:
                return "Must choose at least one winner."
            if n > len(candidates):
                return "Number of winners cannot be more than the number of candidates."
        except ValueError:
            return "Number of winners must be an integer."
        return None

    def blank_ballot(self) -> RankedBallot:
        return RankedBallot(self)

    def tabulate(self, ballots: Iterable[Ballot]) -> tuple[list[str], str]:
        desired_winners = int(self.method_params[NUMBER_OF_WINNERS])
        active_candidates = set(self.candidates)
        elected_candidates: list[str] = []
        lines: list[str] = []

        aggregated_ballots: dict[tuple[str, ...], Fraction] = {}
        for ballot in ballots:
            ranking_tuple = tuple(ballot.ranking)
            aggregated_ballots[ranking_tuple] = aggregated_ballots.get(
                ranking_tuple, 0
            ) + Fraction(1)

        round_num = 1
        exhausted = Fraction(0)

        while True:
            lines.append(f"**Round {round_num}:**")
            lines.append(f"Active candidates: {', '.join(sorted(active_candidates))}")

            counts = {c: 0 for c in active_candidates}
            total_active = Fraction(0)
            for ranking, weight in aggregated_ballots.items():
                counts[ranking[0]] = counts.get(ranking[0], 0) + weight
                total_active += weight

            quota = total_active / Fraction(
                desired_winners - len(elected_candidates) + 1
            )

            lines.append(
                f"Active ballots: {float(total_active):.2g}, exhausted: {float(exhausted):.2g}"
            )

            sorted_candidates = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            if total_active > 0:
                lines.append("Current first-preference counts:")
                for c, v in sorted_candidates:
                    lines.append(
                        f" - {c}: {float(v):.2g} ({float(v / total_active):.2%})"
                    )

            max_count = sorted_candidates[0][1]
            min_count = sorted_candidates[-1][1]

            if max_count > quota:
                winners = [c for c, v in sorted_candidates if v == max_count]
                winner = random.choice(winners)
                if len(winners) > 1:
                    lines.append(
                        f"Multiple winners with equal votes. Randomly selected **{winner}**."
                    )
                lines.append(
                    f"Candidate **{winner}** exceeded {float(100 * quota / total_active):.2g}% ({float(quota):.2g} votes) and is elected."
                )
                elected_candidates.append(winner)

                elim = winner
                quota_fraction = quota / max_count
            else:
                losers = [c for c, v in sorted_candidates if v == min_count]
                loser = random.choice(losers)
                if len(losers) > 1:
                    lines.append(
                        f"Multiple candidates tied for last place. Randomly selected **{loser}** to eliminate."
                    )
                lines.append(f"Candidate **{loser}** is eliminated.")
                elim = loser
                quota_fraction = 0

            active_candidates.remove(elim)

            if len(active_candidates) <= desired_winners - len(elected_candidates):
                for candidate in active_candidates:
                    lines.append(f"Candidate **{candidate}** is elected.")
                elected_candidates.extend(active_candidates)
                active_candidates.clear()
                break

            if len(elected_candidates) >= desired_winners:
                break

            if quota_fraction > 0:
                lines.append(
                    f"Redistributing surplus of {float(max_count - quota):.2g} votes from {elim}."
                )

            new_aggregated: dict[tuple[str, ...], float] = {}
            for ranking, weight in aggregated_ballots.items():
                if ranking[0] == elim:
                    weight *= 1 - quota_fraction
                new_ranking = tuple(c for c in ranking if c != elim)
                if new_ranking:
                    new_aggregated[new_ranking] = (
                        new_aggregated.get(new_ranking, 0) + weight
                    )
                else:
                    exhausted += weight

            aggregated_ballots = new_aggregated

            round_num += 1

        return list(elected_candidates), "\n".join(lines)
