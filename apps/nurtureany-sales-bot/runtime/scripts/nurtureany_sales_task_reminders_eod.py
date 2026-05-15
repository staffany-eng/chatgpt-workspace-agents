#!/usr/bin/env python3
"""EOD wrapper for the NurtureAny HubSpot task reminder digest.

The underlying job prints `NurtureAny automation:`, calls
`list_due_hubspot_sales_task_reminders`, and treats HubSpot Task hs_timestamp as
truth until hs_task_status=COMPLETED.
"""

from __future__ import annotations

import sys

from nurtureany_sales_task_reminders import main


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--mode" not in args:
        args = ["--mode", "eod", *args]
    raise SystemExit(main(args))
