import sys

from app.agent.agent import run


def main():
    if len(sys.argv) > 1:
        print(run(" ".join(sys.argv[1:])))
        return

    while True:
        query = input("you> ").strip()
        if query in {"exit", "quit"}:
            break
        if query:
            print("agent>", run(query))


if __name__ == "__main__":
    main()