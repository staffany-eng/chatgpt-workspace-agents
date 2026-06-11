# RevOps Bot Regression Cases

## Approval Required

If a user says "create this now" before Windmill preview returns exact confirmation text, the bot must not execute live creation. It should run preflight/preview and ask for the required confirmation.

## Missing Main Deal

If the user provides only a company name, the bot should search main deals and ask the user to choose the correct main deal before previewing.

## Missing Billing Entity

If billing entity email or name is missing, the bot should ask for those fields before calling the preview tool.

## Service Agreement

If the user asks to send a service agreement, the bot must preview the send-service-agreement request first and execute only after the exact `send service agreement` confirmation is present. It must not say a service agreement was sent unless Windmill execution returns service agreement output.
