"""Reuse the real signed OCR/review/restart journey for retention acceptance."""
from scripts.m5_benchmark_live_acceptance import main as signed_journey
from scripts.retention_live_checks import check_retention


def main():
    signed_journey(retention_check=check_retention)


if __name__ == "__main__":
    main()
