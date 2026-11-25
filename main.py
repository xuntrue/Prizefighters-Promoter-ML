from analysis import dataset_overview

def main():
    dataset_overview.run(n=10, sample_size=5, bin_years=10, seed=None)

if __name__ == "__main__":
    main()