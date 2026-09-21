# SVA Matrix Squad — Architecture

## Main Flow

Main Menu
→ Feature Selection
→ AI / Task Agent
→ Controller
→ AI Provider
→ Result

## Universal Testing Flow

SCAN
→ DETECT
→ PLAN
→ TEST
→ ANALYZE
→ REPAIR
→ RETEST
→ VERIFY
→ REPORT

## Testing Components

sva_engine/testing/
- detector.py
- planner.py
- runner.py
- parser.py
- repair.py
- repair_executor.py
- loop.py
- reporter.py

## Principles
- Keep existing features working.
- Keep Task Agent separate from normal chat.
- Use structured execution.
- Never silently execute uncontrolled commands.
