"""
When will it ship?

Forecasts a finish date by playing the rest of a project out thousands of
times. Each simulated week picks a real past week at random and assumes the
team gets that much done. The spread of finishing weeks is the forecast.

    python forecast.py --remaining 60
    python forecast.py --remaining 60 --history my_team.csv --chart forecast.png
"""

import argparse
import csv
import random
import sys
from collections import Counter
from datetime import date, datetime, timedelta

MAX_WEEKS = 520  # ten years. If a run gets here, something is wrong with the input.


def load_history(path):
    """Read weekly output from a CSV with a 'completed' column. Returns a list of ints."""
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "completed" not in reader.fieldnames:
            raise ValueError(f"{path} needs a column called 'completed'")
        history = []
        for line, row in enumerate(reader, start=2):
            value = (row["completed"] or "").strip()
            if value == "":
                continue  # skip blank rows
            try:
                number = int(value)
            except ValueError:
                raise ValueError(f"{path}, line {line}: '{value}' is not a whole number") from None
            if number < 0:
                raise ValueError(f"{path}, line {line}: completed can't be negative")
            history.append(number)
    check_history(history)
    return history


def check_history(history):
    if len(history) < 4:
        raise ValueError("Need at least 4 weeks of history to say anything useful")
    if sum(history) == 0:
        raise ValueError("Every week in the history is zero, so the work would never finish")


def simulate(remaining, history, runs=2000, seed=None):
    """Play the project out `runs` times. Returns the finishing week of every run, sorted."""
    if remaining <= 0:
        raise ValueError("Items remaining has to be more than zero")
    if runs <= 0:
        raise ValueError("Runs has to be more than zero")
    check_history(history)

    rng = random.Random(seed)
    results = []
    for _ in range(runs):
        left, weeks = remaining, 0
        while left > 0 and weeks < MAX_WEEKS:
            left -= rng.choice(history)  # one random past week
            weeks += 1
        results.append(weeks)
    results.sort()
    return results


def percentile(sorted_results, pct):
    """The week by which `pct` percent of runs had finished."""
    if not 0 < pct <= 100:
        raise ValueError("Confidence has to be between 1 and 100")
    index = max(0, -(-len(sorted_results) * pct // 100) - 1)  # ceiling, then zero-based
    return sorted_results[int(index)]


def finish_date(start, weeks):
    return start + timedelta(weeks=weeks)


def text_chart(results, marks, width=40):
    """A sideways histogram for the terminal. `marks` maps a week to its label."""
    counts = Counter(results)
    tallest = max(counts.values())
    lines = []
    for week in range(results[0], results[-1] + 1):
        n = counts.get(week, 0)
        bar = "#" * max(1 if n else 0, round(n / tallest * width))
        share = f"{n / len(results):5.1%}"
        lines.append(f"  week {week:>3}  {share}  {bar}  {marks.get(week, '')}".rstrip())
    return "\n".join(lines)


def save_chart(results, levels, path, title):
    """Dot histogram as a PNG. One dot is a batch of runs. Needs matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        raise SystemExit("The chart needs matplotlib. Install it with: pip install matplotlib")

    counts = Counter(results)
    per_dot = max(1, len(results) // 100)
    p_low, p_high = percentile(results, levels[0]), percentile(results, levels[-1])

    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=160)
    most = max(round(n / per_dot) for n in counts.values())
    across = max(1, -(-most // 14))          # dots side by side in one week, so columns stay short
    gap = 0.8 / across
    tallest = 0
    for week in range(results[0], results[-1] + 1):
        dots = round(counts.get(week, 0) / per_dot)
        xs = [week + (k % across - (across - 1) / 2) * gap for k in range(dots)]
        ys = [k // across + 1 for k in range(dots)]
        tallest = max(tallest, max(ys, default=0))
        if week <= p_low:
            ax.scatter(xs, ys, s=30, color="black")
        elif week <= p_high:
            ax.scatter(xs, ys, s=30, color="#a3a3a3")
        else:
            ax.scatter(xs, ys, s=30, facecolors="none", edgecolors="black", linewidths=1)

    labels = {}
    for level in levels:                      # two levels can land on the same week
        labels.setdefault(percentile(results, level), []).append(f"{level}%")
    for week, names in labels.items():
        ax.annotate(" / ".join(names), (week, tallest + 1.5), ha="center", color="#1433ff", fontsize=10, fontweight="bold")
    ax.set_ylim(0, tallest + 3)
    ax.set_xlabel("Weeks from now")
    ax.set_yticks([])
    ax.set_xticks(range(results[0], results[-1] + 1))
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_title(title, loc="left", fontsize=11)
    fig.text(0.125, 0.01, f"One dot is {per_dot} simulated runs. Black finishes by the {levels[0]}% mark, "
                           f"grey by the {levels[-1]}% mark, hollow runs later.", fontsize=8, color="#5f5f5f")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Forecast a finish date from past weekly output.")
    parser.add_argument("--remaining", type=int, required=True, help="how many items are left to do")
    parser.add_argument("--history", default="sample_history.csv", help="CSV with a 'completed' column, one row per week")
    parser.add_argument("--runs", type=int, default=2000, help="how many times to play the project out (default 2000)")
    parser.add_argument("--start", default=None, help="date to count from, YYYY-MM-DD (default today)")
    parser.add_argument("--confidence", type=int, nargs="+", default=[50, 85, 95], help="confidence levels to report")
    parser.add_argument("--seed", type=int, default=None, help="fix the random numbers so a run can be repeated")
    parser.add_argument("--chart", default=None, help="save a chart to this PNG file")
    args = parser.parse_args(argv)

    try:
        history = load_history(args.history)
        start = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else date.today()
        levels = sorted(set(args.confidence))
        results = simulate(args.remaining, history, args.runs, args.seed)
        answers = [(level, percentile(results, level)) for level in levels]
    except FileNotFoundError:
        print(f"Can't find the history file '{args.history}'", file=sys.stderr)
        return 1
    except (ValueError, OSError) as problem:
        print(f"Can't run the forecast: {problem}", file=sys.stderr)
        return 1

    print(f"\n{args.remaining} items left. {args.runs:,} simulated runs, drawn from {len(history)} weeks of history "
          f"({min(history)} to {max(history)} a week, {sum(history) / len(history):.1f} on average).\n")
    marks = {}
    for level, week in answers:
        marks[week] = (marks.get(week, "<- ") + f"{level}% ").rstrip() + " "
    print(text_chart(results, {w: m.strip() for w, m in marks.items()}))
    print()
    for level, week in answers:
        print(f"  {level:>3}% of runs finished within {week} weeks, by {finish_date(start, week):%b %d, %Y}")
    print(f"\nThe average-speed guess would be {args.remaining / (sum(history) / len(history)):.1f} weeks. "
          f"Promise the {levels[-1]}% date, not that one.\n")

    if args.chart:
        save_chart(results, levels, args.chart, f"{args.remaining} items left, {args.runs:,} runs")
        print(f"Chart saved to {args.chart}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
