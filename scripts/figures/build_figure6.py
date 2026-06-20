from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
def main():
    print({'figure_source_status': str((ROOT / 'data/figure_source_data/figure_source_data_status.csv').relative_to(ROOT)), 'note': 'Source-data/status wrapper; high-resolution final artwork excluded.'})
if __name__ == '__main__':
    main()
