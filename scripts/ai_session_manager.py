#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
from datetime import datetime
import urllib.request
import urllib.error

class AISessionManager:
    def __init__(self, root_dir=None):
        self.root_dir = root_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.docs_dir = os.path.join(self.root_dir, "docs")
        
        # Absolute paths for all docs
        self.paths = {
            "state": os.path.join(self.docs_dir, "PROJECT_STATE.md"),
            "handoff": os.path.join(self.docs_dir, "AI_HANDOFF.md"),
            "changelog": os.path.join(self.docs_dir, "CHANGELOG.md"),
            "next_tasks": os.path.join(self.docs_dir, "NEXT_TASKS.md"),
            "known_issues": os.path.join(self.docs_dir, "KNOWN_ISSUES.md"),
            "current_sprint": os.path.join(self.docs_dir, "CURRENT_SPRINT.md"),
            "contract": os.path.join(self.docs_dir, "AI_CONTRACT.md"),
            "roadmap": os.path.join(self.docs_dir, "ROADMAP.md")
        }

    def _get_git_branch(self):
        try:
            res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                                 cwd=self.root_dir, capture_output=True, text=True, check=True)
            return res.stdout.strip()
        except Exception:
            return "unknown"

    def _get_modified_files(self):
        try:
            res = subprocess.run(["git", "status", "--porcelain"], 
                                 cwd=self.root_dir, capture_output=True, text=True, check=True)
            files = []
            for line in res.stdout.splitlines():
                if line.strip():
                    parts = line.strip().split(maxsplit=1)
                    if len(parts) == 2:
                        files.append(parts[1])
            return files
        except Exception:
            return []

    def start_session(self):
        print("=" * 60)
        print("          FRIDAY AI Session Manager - STARTING SESSION          ")
        print("=" * 60)
        
        branch = self._get_git_branch()
        print(f"[*] Detected Git Branch: {branch}")
        
        # Print project state
        if os.path.exists(self.paths["state"]):
            print("\n--- PROJECT STATE SUMMARY ---")
            with open(self.paths["state"], "r") as f:
                content = f.read()
                # Print first 25 lines of Project State
                lines = content.splitlines()
                for line in lines[:20]:
                    print(line)
                if len(lines) > 20:
                    print("...")
        else:
            print("[!] PROJECT_STATE.md not found.")

        # Print current sprint goal
        if os.path.exists(self.paths["current_sprint"]):
            print("\n--- CURRENT SPRINT ---")
            with open(self.paths["current_sprint"], "r") as f:
                content = f.read()
                lines = content.splitlines()
                for line in lines[:15]:
                    print(line)
        else:
            print("[!] CURRENT_SPRINT.md not found.")
            
        print("\n[*] Startup checks completed. Please check docs/AI_CONTRACT.md for details.")
        print("=" * 60)

    def end_session(self, model_name="AntiGravity", duration="1 hour", tasks_completed=None, notes=None):
        print("=" * 60)
        print("          FRIDAY AI Session Manager - ENDING SESSION          ")
        print("=" * 60)
        
        timestamp = datetime.utcnow().isoformat() + "Z"
        branch = self._get_git_branch()
        modified_files = self._get_modified_files()
        
        print(f"[*] Recording session under branch: {branch}")
        print(f"[*] Last update timestamp: {timestamp}")
        
        # 1. Update PROJECT_STATE.md
        if os.path.exists(self.paths["state"]):
            with open(self.paths["state"], "r") as f:
                content = f.read()
            
            # Find and replace "Last Updated: ..."
            new_content = []
            for line in content.splitlines():
                if line.startswith("- **Last Updated**:") or line.startswith("- **Last Updated:**"):
                    new_content.append(f"- **Last Updated**: {timestamp}")
                elif line.startswith("- **Current Branch**:") or line.startswith("- **Current Branch:**"):
                    new_content.append(f"- **Current Branch**: {branch}")
                else:
                    new_content.append(line)
            
            with open(self.paths["state"], "w") as f:
                f.write("\n".join(new_content) + "\n")
            print("[+] Updated docs/PROJECT_STATE.md")

        # 2. Append to AI_HANDOFF.md
        if os.path.exists(self.paths["handoff"]):
            handoff_entry = f"""
---

### Session: {model_name} (End Timestamp: {timestamp})
- **Model**: {model_name}
- **Date**: {datetime.utcnow().strftime('%Y-%m-%d')}
- **Duration**: {duration}
- **Tasks Completed**:
"""
            if tasks_completed:
                for task in tasks_completed:
                    handoff_entry += f"  - {task}\n"
            else:
                handoff_entry += "  - Completed tasks successfully.\n"
                
            handoff_entry += f"- **Files Modified**:\n"
            if modified_files:
                for f in modified_files:
                    handoff_entry += f"  - {f}\n"
            else:
                handoff_entry += "  - No modifications recorded.\n"
                
            handoff_entry += f"- **Notes**: {notes or 'No session notes provided.'}\n"
            handoff_entry += f"- **Recommended next actions**:\n"
            handoff_entry += f"  - Review sprint tasks in docs/CURRENT_SPRINT.md.\n"
            
            with open(self.paths["handoff"], "a") as f:
                f.write(handoff_entry)
            print("[+] Appended to docs/AI_HANDOFF.md")
            
        # 3. Add entries to CHANGELOG.md if modified
        if modified_files and os.path.exists(self.paths["changelog"]):
            # Add a small note in the changelog
            with open(self.paths["changelog"], "r") as f:
                changelog_content = f.read()
            
            # Simple prepend under the top header
            lines = changelog_content.splitlines()
            insert_idx = 0
            for idx, line in enumerate(lines):
                if line.startswith("## [") or line.startswith("## "):
                    insert_idx = idx
                    break
            
            if insert_idx > 0:
                new_changelog = lines[:insert_idx]
                new_changelog.append(f"### Added (Session {model_name})")
                for f in modified_files:
                    new_changelog.append(f"- Modified: {f}")
                new_changelog.append("")
                new_changelog.extend(lines[insert_idx:])
                with open(self.paths["changelog"], "w") as f:
                    f.write("\n".join(new_changelog) + "\n")
                print("[+] Updated docs/CHANGELOG.md")
                
        print("\n[*] Session ended successfully. Please commit your changes to git.")
        print("=" * 60)

    def health_check(self):
        print("=" * 60)
        print("          FRIDAY AI Session Manager - HEALTH CHECK          ")
        print("=" * 60)
        
        status = {"pytest": "UNKNOWN", "gateway": "UNKNOWN", "api": "UNKNOWN", "desktop": "UNKNOWN"}
        
        # 1. pytest check
        print("[*] Running pytest suite...")
        try:
            res = subprocess.run([".venv/bin/python3", "-m", "pytest", "tests/test_autonomous_dev/"], 
                                 cwd=self.root_dir, capture_output=True, text=True)
            if res.returncode == 0:
                print("  [+] Pytest check passed successfully!")
                status["pytest"] = "PASSED"
            else:
                print(f"  [x] Pytest check failed (code {res.returncode})")
                status["pytest"] = "FAILED"
        except Exception as e:
            print(f"  [x] Could not run pytest: {e}")
            status["pytest"] = "ERROR"

        # 2. Gateway check (port 5000)
        print("[*] Verifying Gateway port 5000...")
        try:
            req = urllib.request.Request("http://localhost:5000/health", method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    print("  [+] Gateway port check passed!")
                    status["gateway"] = "HEALTHY"
                else:
                    print(f"  [x] Gateway port check returned status {response.status}")
                    status["gateway"] = "UNHEALTHY"
        except urllib.error.URLError as e:
            print(f"  [?] Gateway is unreachable on port 5000 (URLError: {e.reason})")
            status["gateway"] = "DOWN"
        except Exception as e:
            print(f"  [x] Gateway check failed with error: {e}")
            status["gateway"] = "ERROR"

        # 3. API check (port 8000)
        print("[*] Verifying API port 8000...")
        try:
            req = urllib.request.Request("http://localhost:8000/health", method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    print("  [+] API port check passed!")
                    status["api"] = "HEALTHY"
                else:
                    print(f"  [x] API port check returned status {response.status}")
                    status["api"] = "UNHEALTHY"
        except urllib.error.URLError as e:
            print(f"  [?] API is unreachable on port 8000 (URLError: {e.reason})")
            status["api"] = "DOWN"
        except Exception as e:
            print(f"  [x] API check failed with error: {e}")
            status["api"] = "ERROR"

        # 4. Desktop app package check
        print("[*] Verifying Desktop app structure...")
        desktop_package = os.path.join(self.root_dir, "apps/desktop/package.json")
        if os.path.exists(desktop_package):
            print("  [+] Desktop package.json exists!")
            status["desktop"] = "PRESENT"
        else:
            print("  [x] Desktop package.json is missing!")
            status["desktop"] = "MISSING"
            
        print("\n--- HEALTH CHECK SUMMARY ---")
        for key, val in status.items():
            print(f"  - {key.upper()}: {val}")
        print("=" * 60)
        return status

    def generate_report(self):
        report_path = os.path.join(self.root_dir, "SESSION_REPORT.md")
        timestamp = datetime.utcnow().isoformat() + "Z"
        modified = self._get_modified_files()
        branch = self._get_git_branch()
        
        report_content = f"""# FACS Session Report

Generated at: {timestamp}
Branch: {branch}

## Modified Files
"""
        if modified:
            for f in modified:
                report_content += f"- {f}\n"
        else:
            report_content += "No modified files detected.\n"
            
        report_content += "\n## System Status Overview\n"
        health = self.health_check()
        for k, v in health.items():
            report_content += f"- **{k.upper()}**: {v}\n"
            
        with open(report_path, "w") as f:
            f.write(report_content)
        print(f"[+] Session report generated successfully at: {report_path}")

def main():
    parser = argparse.ArgumentParser(description="FRIDAY AI Continuity System (FACS) Session Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Start command
    subparsers.add_parser("start", help="Initialize and start a new AI developer session")
    
    # End command
    end_parser = subparsers.add_parser("end", help="Complete and save the current AI developer session")
    end_parser.add_argument("--model", default="AntiGravity", help="Name of the AI developer model")
    end_parser.add_argument("--duration", default="1 hour", help="Estimated session duration")
    end_parser.add_argument("--tasks", nargs="+", help="List of tasks completed during this session")
    end_parser.add_argument("--notes", help="Handoff notes for the next session")
    
    # Health command
    subparsers.add_parser("health", help="Execute test suite and port validation checks")
    
    # Report command
    subparsers.add_parser("report", help="Generate a comprehensive SESSION_REPORT.md file")
    
    args = parser.parse_args()
    manager = AISessionManager()
    
    if args.command == "start":
        manager.start_session()
    elif args.command == "end":
        manager.end_session(model_name=args.model, duration=args.duration, tasks_completed=args.tasks, notes=args.notes)
    elif args.command == "health":
        manager.health_check()
    elif args.command == "report":
        manager.generate_report()

if __name__ == "__main__":
    main()
