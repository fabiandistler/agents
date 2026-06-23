import csv
import statistics


def build_monthly_report(csv_path, output_path):
    rows = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["status"] != "active":
                continue
            row["revenue"] = float(row["revenue"])
            row["cost"] = float(row["cost"])
            row["profit"] = row["revenue"] - row["cost"]
            rows.append(row)

    total_revenue = sum(r["revenue"] for r in rows)
    total_cost = sum(r["cost"] for r in rows)
    avg_profit = statistics.mean(r["profit"] for r in rows) if rows else 0

    lines = []
    lines.append("Monthly Report")
    lines.append(f"Active records: {len(rows)}")
    lines.append(f"Revenue: {total_revenue:.2f}")
    lines.append(f"Cost: {total_cost:.2f}")
    lines.append(f"Average profit: {avg_profit:.2f}")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    return output_path
