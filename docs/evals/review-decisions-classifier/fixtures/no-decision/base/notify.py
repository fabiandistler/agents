"""Send the daily export report by mail."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipient", help="address that should recieve the report")
    args = parser.parse_args()
    print(f"would mail the report to {args.recipient}")


if __name__ == "__main__":
    main()
