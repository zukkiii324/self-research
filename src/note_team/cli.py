from __future__ import annotations

import argparse
from pathlib import Path

from note_team.orchestrator import WorkflowRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="note-team",
        description="Note向け記事制作を複数エージェント体制で進めるCLI",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="project root directory",
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    validate_parser = subparsers.add_parser("validate", help="team config and prompt files を検証する")
    validate_parser.add_argument(
        "--team",
        default="config/note_editorial_team.json",
        help="path to the team configuration file",
    )

    run_parser = subparsers.add_parser("run", help="briefから執筆ワークフローを実行する")
    run_parser.add_argument("--brief", required=True, help="path to article brief json")
    run_parser.add_argument(
        "--team",
        default="config/note_editorial_team.json",
        help="path to the team configuration file",
    )
    run_parser.add_argument(
        "--output-root",
        default="runs",
        help="directory to write run artifacts to",
    )
    run_parser.add_argument(
        "--mode",
        default="mock",
        choices=["mock", "manual", "command"],
        help="execution mode",
    )
    run_parser.add_argument(
        "--runner-command",
        help="shell command to execute per stage when mode=command; prompt is passed via stdin",
    )
    run_parser.add_argument(
        "--run-name",
        help="custom run name used for the output directory slug",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    team_path = project_root / args.team
    runner = WorkflowRunner(project_root=project_root, team_config_path=team_path)

    if args.subcommand == "validate":
        findings = runner.validate()
        if findings:
            for finding in findings:
                print(f"- {finding}")
        else:
            print("validation passed")
        return 0

    if args.subcommand == "run":
        run_dir = runner.run(
            brief_path=project_root / args.brief,
            output_root=project_root / args.output_root,
            mode=args.mode,
            run_name=args.run_name,
            command=args.runner_command,
        )
        print(run_dir)
        return 0

    parser.error(f"unsupported command: {args.subcommand}")
    return 2
