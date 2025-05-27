from src.log_collector import LogCollector


def main():
    collector = LogCollector()
    collector.start_collection()


if __name__ == "__main__":
    main()