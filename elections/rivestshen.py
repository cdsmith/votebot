from election import Election
from ballots.ranked import RankedBallot
import numpy as np
from scipy.optimize import linprog
import random


class RivestShenGTElection(Election):
    def blank_ballot(self) -> RankedBallot:
        return RankedBallot(self)

    def tabulate(self) -> tuple[list[str], str]:
        if not self.candidates:
            return [], "No candidates were found."

        m = len(self.candidates)
        ballots = list(self.submitted_ballots.values())

        M = [[0] * m for _ in range(m)]

        for i in range(m):
            for j in range(m):
                if i == j:
                    M[i][j] = 0
                else:
                    i_pref_j = 0
                    j_pref_i = 0
                    for ballot in ballots:
                        ranking = ballot.ranking
                        try:
                            i_pos = ranking.index(self.candidates[i])
                        except ValueError:
                            i_pos = len(ranking)
                        try:
                            j_pos = ranking.index(self.candidates[j])
                        except ValueError:
                            j_pos = len(ranking)

                        if i_pos < j_pos:
                            i_pref_j += 1
                        elif j_pos < i_pos:
                            j_pref_i += 1
                    M[i][j] = i_pref_j - j_pref_i

        min_val = min(min(row) for row in M)
        if min_val <= 0:
            w = 1 - min_val
        else:
            w = 0.0

        M_prime = [[M[i][j] + w for j in range(m)] for i in range(m)]

        c = [1.0] * m
        A_ub = (-1) * np.array(M_prime, dtype=float).T
        b_ub = -1 * np.ones(m, dtype=float)
        bounds = [(0, None)] * m
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")

        if not res.success:
            return [], "No optimal solution found for the Rivest-Shen GT equilibrium."

        p = res.x
        p_star = [w * val for val in p]

        total = sum(p_star)
        if total > 0:
            p_dist = [x / total for x in p_star]

        winner = random.choices(self.candidates, weights=p_dist, k=1)[0]

        lines = []
        lines.append("**Margin Matrix M:**")
        lines.append("```")
        for i, c1 in enumerate(self.candidates):
            row_str = []
            for j, c2 in enumerate(self.candidates):
                row_str.append(f"{M[i][j]:+d}")
            lines.append(f"{c1}: " + " ".join(row_str))
        lines.append("```")

        lines.append("")
        lines.append("**GTO equilibrium win probabilities:**")
        for c, val in zip(self.candidates, p_dist):
            lines.append(f"{c}: {val:.2%}")

        lines.append("")
        lines.append(f"**Winner:** {winner}")

        return [winner], "\n".join(lines)
