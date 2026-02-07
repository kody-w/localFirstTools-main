#!/usr/bin/env python3
"""
Buzzsaw v3 Production Statistics Generator

Analyzes the repository to generate production statistics for the Buzzsaw game development pipeline.
Scans git log, analyzes HTML files in apps/games-puzzles/, runs quality checks, and outputs JSON stats.

Usage:
    python3 scripts/buzzsaw_stats.py
    python3 scripts/buzzsaw_stats.py --watch
    python3 scripts/buzzsaw_stats.py --output custom-path.json
"""

import os
import sys
import re
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import time
import argparse


class BuzzsawStatsGenerator:
    """Generates production statistics for Buzzsaw v3 game development pipeline."""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.games_dir = self.repo_root / "apps" / "games-puzzles"
        self.output_path = self.repo_root / "apps" / "creative-tools" / "buzzsaw-stats.json"

    def scan_git_log(self) -> List[Dict]:
        """Scan git log for Buzzsaw/Wave commits."""
        waves = []
        try:
            # Get all commits with "Buzzsaw" or "Wave" in message
            result = subprocess.run(
                ["git", "log", "--all", "--pretty=format:%H|%s|%ad", "--date=short"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                print(f"Warning: git log failed: {result.stderr}")
                return []

            wave_pattern = re.compile(r'(buzzsaw|wave)\s*(\d+|v?\d+)?', re.IGNORECASE)

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) < 3:
                    continue

                commit_hash, message, date = parts[0], parts[1], parts[2]

                match = wave_pattern.search(message)
                if match:
                    wave_num = match.group(2) if match.group(2) else "unknown"
                    waves.append({
                        "name": f"Wave {wave_num}" if wave_num != "unknown" else message[:50],
                        "commit": commit_hash[:8],
                        "date": date,
                        "message": message
                    })
        except subprocess.TimeoutExpired:
            print("Warning: git log timed out")
        except Exception as e:
            print(f"Warning: git log error: {e}")

        return waves

    def analyze_html_file(self, file_path: Path) -> Dict:
        """Analyze a single HTML game file for stats and quality checks."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            size = file_path.stat().st_size
            lines = content.count('\n') + 1

            # Quality checks
            checks = {
                "doctype": bool(re.search(r'<!DOCTYPE\s+html>', content, re.IGNORECASE)),
                "localstorage": "localStorage" in content,
                "canvas": bool(re.search(r'<canvas|getContext\s*\(\s*[\'"]2d', content, re.IGNORECASE)),
                "audio": bool(re.search(r'AudioContext|webkitAudioContext|new Audio\(', content)),
                "raf": "requestAnimationFrame" in content,
                "no_external_deps": not bool(re.search(r'<script[^>]+src\s*=|<link[^>]+href\s*=.*?\.css', content)),
                "has_pause": bool(re.search(r'pause|paused', content, re.IGNORECASE)),
                "has_gameover": bool(re.search(r'game\s*over|gameover|game\s*end', content, re.IGNORECASE))
            }

            # Calculate quality score (0-100)
            quality_score = sum(checks.values()) / len(checks) * 100

            # Extract title from <title> tag or filename
            title_match = re.search(r'<title>([^<]+)</title>', content, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else file_path.stem.replace('-', ' ').title()

            # Get creation date from git or file mtime
            created = self.get_file_creation_date(file_path)

            return {
                "file": file_path.name,
                "title": title,
                "size_bytes": size,
                "lines": lines,
                "quality_score": round(quality_score, 1),
                "checks": checks,
                "created": created
            }
        except Exception as e:
            print(f"Error analyzing {file_path.name}: {e}")
            return None

    def get_file_creation_date(self, file_path: Path) -> str:
        """Get file creation date from git log or file mtime."""
        try:
            result = subprocess.run(
                ["git", "log", "--diff-filter=A", "--format=%ad", "--date=short", "-1", "--", str(file_path)],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass

        # Fallback to file mtime
        mtime = file_path.stat().st_mtime
        return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')

    def calculate_token_estimates(self, games: List[Dict]) -> Dict:
        """Calculate token usage estimates for Claude Code and Copilot CLI."""
        # Claude Code orchestration: ~5000 tokens per game (prompts + validation + coordination)
        claude_tokens_per_game = 5000
        claude_total = len(games) * claude_tokens_per_game

        # Copilot CLI generation: ~4 tokens per line of code (average for Python/JS)
        total_lines = sum(g["lines"] for g in games)
        copilot_total = total_lines * 4

        total_tokens = claude_total + copilot_total
        copilot_percentage = (copilot_total / total_tokens * 100) if total_tokens > 0 else 0

        return {
            "claude_code_orchestration": claude_total,
            "copilot_cli_generation": copilot_total,
            "total": total_tokens,
            "copilot_percentage": round(copilot_percentage, 1)
        }

    def organize_waves(self, games: List[Dict], git_waves: List[Dict]) -> List[Dict]:
        """Organize games into waves based on git commits."""
        # Sort games by creation date
        sorted_games = sorted(games, key=lambda g: g["created"])

        if not git_waves:
            # If no git waves found, create synthetic waves based on dates
            waves = []
            current_wave = []
            current_date = None
            wave_num = 1

            for game in sorted_games:
                if current_date is None:
                    current_date = game["created"]
                    current_wave = [game]
                elif game["created"] == current_date:
                    current_wave.append(game)
                else:
                    # New wave
                    waves.append({
                        "name": f"Wave {wave_num}",
                        "games": len(current_wave),
                        "total_size": sum(g["size_bytes"] for g in current_wave),
                        "date": current_date
                    })
                    wave_num += 1
                    current_date = game["created"]
                    current_wave = [game]

            # Add last wave
            if current_wave:
                waves.append({
                    "name": f"Wave {wave_num}",
                    "games": len(current_wave),
                    "total_size": sum(g["size_bytes"] for g in current_wave),
                    "date": current_date
                })

            return waves
        else:
            # Use git waves (simplified - just use wave metadata)
            wave_dict = {}
            for wave in git_waves:
                wave_name = wave["name"]
                if wave_name not in wave_dict:
                    wave_dict[wave_name] = {
                        "name": wave_name,
                        "games": 0,
                        "total_size": 0,
                        "date": wave["date"]
                    }

            # Distribute games across waves by date
            wave_list = sorted(wave_dict.values(), key=lambda w: w["date"])
            games_per_wave = len(games) // len(wave_list) if wave_list else len(games)

            for i, wave in enumerate(wave_list):
                wave_games = sorted_games[i * games_per_wave:(i + 1) * games_per_wave]
                wave["games"] = len(wave_games)
                wave["total_size"] = sum(g["size_bytes"] for g in wave_games)

            # Add remaining games to last wave
            if wave_list:
                remaining = sorted_games[len(wave_list) * games_per_wave:]
                wave_list[-1]["games"] += len(remaining)
                wave_list[-1]["total_size"] += sum(g["size_bytes"] for g in remaining)

            return wave_list

    def generate_stats(self) -> Dict:
        """Generate complete statistics."""
        print(f"Scanning games directory: {self.games_dir}")

        if not self.games_dir.exists():
            print(f"Error: Games directory not found: {self.games_dir}")
            return None

        # Scan git log for waves
        print("Scanning git log for Buzzsaw/Wave commits...")
        git_waves = self.scan_git_log()
        print(f"Found {len(git_waves)} wave commits")

        # Analyze all HTML files
        print("Analyzing HTML game files...")
        games = []
        html_files = list(self.games_dir.glob("*.html"))

        for i, file_path in enumerate(html_files, 1):
            print(f"  [{i}/{len(html_files)}] {file_path.name}")
            game_data = self.analyze_html_file(file_path)
            if game_data:
                games.append(game_data)

        if not games:
            print("No games found!")
            return None

        # Calculate summary metrics
        total_lines = sum(g["lines"] for g in games)
        total_size = sum(g["size_bytes"] for g in games)
        avg_quality = sum(g["quality_score"] for g in games) / len(games)

        # Calculate token estimates
        token_breakdown = self.calculate_token_estimates(games)

        # Organize waves
        waves = self.organize_waves(games, git_waves)

        # Build output
        stats = {
            "generated": datetime.now().isoformat(),
            "summary": {
                "total_games": len(games),
                "total_lines": total_lines,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "avg_lines": round(total_lines / len(games)),
                "avg_size_kb": round(total_size / len(games) / 1024, 1),
                "avg_quality_score": round(avg_quality, 1),
                "estimated_claude_tokens": token_breakdown["claude_code_orchestration"],
                "estimated_copilot_tokens": token_breakdown["copilot_cli_generation"],
                "delegation_ratio": round(token_breakdown["copilot_percentage"] / 100, 2),
                "waves_completed": len(waves)
            },
            "games": sorted(games, key=lambda g: g["created"], reverse=True),
            "waves": waves,
            "token_breakdown": token_breakdown
        }

        return stats

    def save_stats(self, stats: Dict, output_path: Path = None):
        """Save statistics to JSON file."""
        if output_path is None:
            output_path = self.output_path

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        print(f"\nStats saved to: {output_path}")
        print(f"  Total games: {stats['summary']['total_games']}")
        print(f"  Total lines: {stats['summary']['total_lines']:,}")
        print(f"  Total size: {stats['summary']['total_size_mb']} MB")
        print(f"  Avg quality: {stats['summary']['avg_quality_score']}")
        print(f"  Copilot delegation: {stats['summary']['delegation_ratio']*100:.1f}%")
        print(f"  Waves: {stats['summary']['waves_completed']}")

    def watch_mode(self, interval: int = 30):
        """Continuously regenerate stats every interval seconds."""
        print(f"Starting watch mode (regenerate every {interval}s, Ctrl+C to stop)...")
        try:
            while True:
                print(f"\n{'='*60}")
                print(f"Regenerating stats at {datetime.now().strftime('%H:%M:%S')}")
                print('='*60)

                stats = self.generate_stats()
                if stats:
                    self.save_stats(stats)

                print(f"\nWaiting {interval} seconds...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nWatch mode stopped.")


def main():
    parser = argparse.ArgumentParser(description="Generate Buzzsaw v3 production statistics")
    parser.add_argument("--watch", action="store_true", help="Regenerate stats every 30 seconds")
    parser.add_argument("--interval", type=int, default=30, help="Watch mode interval in seconds (default: 30)")
    parser.add_argument("--output", type=str, help="Custom output path for JSON file")
    args = parser.parse_args()

    # Detect repo root (script is in scripts/ subdirectory)
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent

    generator = BuzzsawStatsGenerator(repo_root)

    if args.output:
        generator.output_path = Path(args.output)

    if args.watch:
        generator.watch_mode(interval=args.interval)
    else:
        stats = generator.generate_stats()
        if stats:
            generator.save_stats(stats)
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
