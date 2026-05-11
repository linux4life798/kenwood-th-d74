#!/usr/bin/env python3
"""Command-line updater flow for TH-D74 firmware programs."""

from __future__ import annotations

import argparse
from pathlib import Path

from firmware import FirmwareDescriptor
import fldm
import update_bad
import update_exe
import update_flat
import update_jump

type ProgramPayload = tuple[FirmwareDescriptor, tuple[fldm.Segment, ...]]


def load_program(program: Path) -> ProgramPayload:
    """Load the selected updater payload format."""
    if program == Path(update_bad.SPECIAL_WORD):
        return update_bad.build()
    if program == Path(update_jump.SPECIAL_WORD):
        return update_jump.build()
    if not program.is_file():
        raise FileNotFoundError(program)
    if update_exe.is_windows_exe(program):
        return update_exe.load(program)
    return update_flat.build(program)


def run(
    program: Path,
    port: str,
    baud: int,
    reply_timeout: float = 2.0,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Run the metadata-driven FLDM flow."""
    firmware_descriptor, segments = load_program(program)

    with fldm.FLDMLoader(
        port,
        baud=baud,
        reply_timeout=reply_timeout,
        verbose=verbose,
    ) as loader:
        print("# Starting unencrypted program mode.")
        loader.unlock()

        print("# Send start-program command.")
        start_program_code = firmware_descriptor.start_program_code
        loader.start_programming(
            0 if start_program_code is None else start_program_code
        )
        # time.sleep(2)  # Show the flashing PROGRAM on display.

        # print("# Select updater target profile.")
        # print(loader.select_target_unit())

        print("# Start timed programming session.")
        loader.start_timed_session()

        print("# Query target profile.")
        target_profile = loader.query_target_profile()
        print(f"# Target profile: {target_profile}")

        print("# Select baud/transfer mode.")
        loader.set_baud_transfer_mode()

        print("# Segments that would be flashed.")
        for segment in segments:
            compatible = target_profile.is_target_compatible(
                segment.descriptor.target_type_mask
            )
            segment.print_dry_run(compatible=compatible)
            if dry_run:
                continue
            if not compatible:
                print(f"# Skip incompatible segment [{segment.index}] {segment.label}.")
                continue
            print(f"# Flash segment [{segment.index}] {segment.label}.")
            loader.program_segment(segment.descriptor, segment.data)

        print("# Send complete command.")
        completion_code = firmware_descriptor.completion_code
        loader.complete(
            fldm.DEFAULT_COMPLETE_CODE if completion_code is None else completion_code
        )


def main() -> None:
    """Parse command-line arguments and run the smoke test."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "program",
        type=Path,
        help='path to the Kenwood updater .exe, flat fw binary, or special command "bad" or "jump"',
    )
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--reply-timeout", type=float, default=2.0)
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="print segment flash operations without programming them",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print raw TX/RX bytes"
    )
    args = parser.parse_args()

    run(
        args.program,
        args.port,
        args.baud,
        args.reply_timeout,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
