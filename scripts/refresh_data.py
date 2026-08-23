#!/usr/bin/env python3
"""Refresh and normalize official CBO and Treasury data snapshots."""

from debt_sim.data import refresh_cli

if __name__ == "__main__":
    refresh_cli()
