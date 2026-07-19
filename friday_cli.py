import requests
import sys
import json

def main():
    if len(sys.argv) < 2:
        print("Usage: python friday_cli.py <command> [args]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "inspect" and len(sys.argv) == 3 and sys.argv[2] == ".":
        prompt = "inspect ."
        url = "http://localhost:5000/autonomous/start"
        try:
            print(f"Sending request to {url} with prompt: '{prompt}'")
            response = requests.post(url, params={"prompt": prompt}, timeout=30)

            if response.status_code == 200:
                print("\n✅ Goal started successfully:")
                print(json.dumps(response.json(), indent=2))
            else:
                print(f"\n❌ Error starting goal (HTTP {response.status_code}):")
                try:
                    print(json.dumps(response.json(), indent=2))
                except json.JSONDecodeError:
                    print(response.text)

        except requests.exceptions.RequestException as e:
            print(f"\n❌ API call failed: {e}")
            print("Please ensure the FRIDAY services are running.")

    elif command == "autonomous":
        print("Command 'autonomous' not yet implemented in this CLI script.")

    else:
        print(f"Unknown command: {' '.join(sys.argv[1:])}")

if __name__ == "__main__":
    main()
