from api.PrizeFighterAPI import PrizeFighterAPI
from analysis import dataset_overview

def main():
    api = PrizeFighterAPI()
    dataset_overview.run(api=api, n=10, sample_size=5, bin_years=5, seed=None)

if __name__ == "__main__":
    main()